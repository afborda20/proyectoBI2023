from fastapi import FastAPI, File, UploadFile
from pydantic import BaseModel
import joblib
import io
import pandas as pd
from num2words import num2words
import unicodedata
import re
import stanza
import nltk
nltk.download('stopwords')
from nltk.corpus import stopwords
from sklearn.base import BaseEstimator, TransformerMixin

app = FastAPI()

#Se carga el modelo de prediccion construido
model = joblib.load("ModeloODS.joblib")

class PredictRequest(BaseModel):
    text: str

class CustomPreprocessor(BaseEstimator, TransformerMixin):
    def init(self):
        pass

    def fit(self, X, y=None):
        return self

    def transform(self, X):

        X_processed = self.customPreprocessing(X)
        #Retornar los datos
        return X_processed
    
    #Remplaza los numeros por su representacion en palabras
    def replace_numbers(self, words):
        """Replace all interger occurrences in list of tokenized words with textual representation"""
        new_words = []
        for word in words:
            if word.isdigit():
                new_word = num2words(word, lang='es')
                new_words.append(new_word)
            else:
                new_words.append(word)
        return new_words
    #Remueve todo caracter no latino (conserva espacios y numeros)
    def remove_nonlatin(self, words):
      new_words = []
      for word in words:
        new_word = ''
        for ch in word:
          if unicodedata.name(ch).startswith(('LATIN', 'DIGIT', 'SPACE')):
            new_word += ch
        new_words.append(new_word)
      return new_words

    #Remueve palabras comunes que no aportan informacion
    def remove_stopwords(self, words):
        """Remove stop words from list of tokenized words"""
        new_words = []
        s = set(stopwords.words('spanish'))
        for word in words:
            if word not in s:
                new_words.append(word)
        return new_words

    #Remueve puntuacion
    def remove_punctuation(self, words):
        """Remove punctuation from list of tokenized words"""
        new_words = ''
        for word in words:
                new_words += re.sub(r'[^\w\s]', ' ', word)
        return new_words

     #Procesamiento de cada review usando stanza
    def tokenLemma(self, data):
      data['words'] = data['Textos_espanol'].apply(self.remove_punctuation)
      #Creamos un pipeline para tokenizacion y lematizacion
      nlp = stanza.Pipeline('es', processors = 'tokenize,mwt,pos,lemma', use_gpu=True)
      in_docs = [stanza.Document([], text=d) for d in data.words]
      return nlp(in_docs)

    #Funcion secundaria para procesar cada token
    def procesamientoPalabras(self, words):
        words = self.remove_nonlatin(words)
        words = self.replace_numbers(words)
        words = self.remove_stopwords(words)
        return words

    #Funcion principal para el pre-procesamiento
    def customPreprocessing(self, data):
        out_docs = self.tokenLemma(data)
        palabras = []

        for doc in out_docs:
            reviewAct = []
            for sentence in doc.sentences:
              for word in sentence.words:
                if(word.pos != 'PUNCT' and word.pos != 'SYM'):
                  reviewAct.append(word.lemma.lower())
            palabras.append(reviewAct)
        
        data['words'] = palabras
        data['words'] = data['words'].apply(self.procesamientoPalabras)
        return data


preprocessor = CustomPreprocessor()

@app.post("/predict/")
def predict_csv(file: UploadFile):
    if file.filename.endswith(".csv"):
        # Leer el csv y convertirlo en un dataframe de pandas
        csv_data = pd.read_csv(io.StringIO(file.file.read().decode("utf-8")))

        #Preprocesamiento
        preprocessed_text = preprocessor.customPreprocessing(csv_data)

        # Preprocess and make predictions for each article
        predictions = model.predict([preprocessed_text])

        return {"predictions": predictions}
    else:
        return {"error": "Solo se soportan archivos csv."}

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
