import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC
from sklearn.metrics import accuracy_score, classification_report
import joblib
import nltk
import os

class ModelTrainer:
    def __init__(self):
        self.vectorizer = TfidfVectorizer(
            max_features=5000,
            stop_words='english',
            ngram_range=(1, 3)
        )
        
    def train_fake_news_model(self, data_path):
        """Train fake news detection model"""
        # Load dataset (you need to provide your dataset)
        df = pd.read_csv(data_path)
        
        # Prepare features and labels
        X = df['text']
        y = df['label']  # 0 for real, 1 for fake
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
        # Vectorize text
        X_train_vectorized = self.vectorizer.fit_transform(X_train)
        X_test_vectorized = self.vectorizer.transform(X_test)
        
        # Train model
        model = RandomForestClassifier(n_estimators=100, random_state=42)
        model.fit(X_train_vectorized, y_train)
        
        # Evaluate
        y_pred = model.predict(X_test_vectorized)
        accuracy = accuracy_score(y_test, y_pred)
        print(f"Fake News Model Accuracy: {accuracy:.2f}")
        print(classification_report(y_test, y_pred))
        
        # Save model
        joblib.dump(model, 'ml_models/fake_news_model.pkl')
        joblib.dump(self.vectorizer, 'ml_models/vectorizer.pkl')
        
        return model

    def train_scam_detection_model(self, data_path):
        """Train scam detection model"""
        # Similar to fake news training but with scam-specific dataset
        df = pd.read_csv(data_path)
        
        X = df['text']
        y = df['is_scam']  # 0 for legitimate, 1 for scam
        
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
        # Use same vectorizer or create new one
        scam_vectorizer = TfidfVectorizer(max_features=5000, stop_words='english')
        X_train_vectorized = scam_vectorizer.fit_transform(X_train)
        X_test_vectorized = scam_vectorizer.transform(X_test)
        
        # Train model (Logistic Regression often works well for scam detection)
        model = LogisticRegression(random_state=42)
        model.fit(X_train_vectorized, y_train)
        
        # Evaluate
        y_pred = model.predict(X_test_vectorized)
        accuracy = accuracy_score(y_test, y_pred)
        print(f"Scam Detection Model Accuracy: {accuracy:.2f}")
        print(classification_report(y_test, y_pred))
        
        # Save model
        joblib.dump(model, 'ml_models/scam_detection_model.pkl')
        
        return model

if __name__ == "__main__":
    trainer = ModelTrainer()
    # Train models (you need to provide your datasets)
    # trainer.train_fake_news_model('data/fake_news_dataset.csv')
    # trainer.train_scam_detection_model('data/scam_dataset.csv')