import re
import nltk
import spacy
import joblib
import numpy as np
from textblob import TextBlob
from sklearn.feature_extraction.text import TfidfVectorizer
from transformers import pipeline
import torch
from newspaper import Article
import requests
from bs4 import BeautifulSoup
import hashlib
import json

class NLPDetector:
    def __init__(self):
        # Download required NLTK data
        nltk.download('punkt')
        nltk.download('stopwords')
        nltk.download('wordnet')
        
        # Load spaCy model
        try:
            self.nlp = spacy.load('en_core_web_sm')
        except:
            spacy.cli.download('en_core_web_sm')
            self.nlp = spacy.load('en_core_web_sm')
        
        # Load pre-trained models
        try:
            self.news_model = joblib.load('ml_models/fake_news_model.pkl')
            self.scam_model = joblib.load('ml_models/scam_detection_model.pkl')
            self.vectorizer = joblib.load('ml_models/vectorizer.pkl')
        except:
            self.news_model = None
            self.scam_model = None
            self.vectorizer = None
        
        # Initialize transformers pipeline for advanced analysis
        self.sentiment_analyzer = pipeline('sentiment-analysis')
        
        # Keywords for scam detection
        self.scam_keywords = [
            'urgent', 'winner', 'prize', 'lottery', 'bank account', 
            'verify', 'password', 'credit card', 'ssn', 'social security',
            'inheritance', 'wire transfer', 'gift card', 'bitcoin',
            'western union', 'money gram', 'tax refund', 'irs',
            'unlock', 'limited time', 'act now', 'guaranteed'
        ]
        
        # Trusted news sources (expand this list)
        self.trusted_sources = [
            'reuters.com', 'apnews.com', 'bbc.com', 'bbc.co.uk',
            'cnn.com', 'nytimes.com', 'wsj.com', 'washingtonpost.com',
            'theguardian.com', 'npr.org', 'politico.com', 'economist.com'
        ]
        
        # Satire sites
        self.satire_sites = [
            'theonion.com', 'clickhole.com', 'babylonbee.com',
            'thebeaverton.com', 'fakingnews.com'
        ]

    def preprocess_text(self, text):
        """Clean and preprocess text"""
        # Convert to lowercase
        text = text.lower()
        
        # Remove URLs
        text = re.sub(r'http\S+|www\S+|https\S+', '', text, flags=re.MULTILINE)
        
        # Remove special characters and digits
        text = re.sub(r'[^\w\s]', '', text)
        text = re.sub(r'\d+', '', text)
        
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        return text

    def extract_features(self, text):
        """Extract features from text for ML models"""
        features = {}
        
        # Length features
        features['text_length'] = len(text)
        features['word_count'] = len(text.split())
        features['sentence_count'] = len(nltk.sent_tokenize(text))
        
        # Sentiment analysis
        blob = TextBlob(text)
        features['sentiment_polarity'] = blob.sentiment.polarity
        features['sentiment_subjectivity'] = blob.sentiment.subjectivity
        
        # POS tags distribution
        doc = self.nlp(text)
        pos_counts = {}
        for token in doc:
            pos_counts[token.pos_] = pos_counts.get(token.pos_, 0) + 1
        
        features['noun_count'] = pos_counts.get('NOUN', 0)
        features['verb_count'] = pos_counts.get('VERB', 0)
        features['adj_count'] = pos_counts.get('ADJ', 0)
        
        # Named entities
        entities = [ent.label_ for ent in doc.ents]
        features['entity_count'] = len(entities)
        features['person_entities'] = entities.count('PERSON')
        features['org_entities'] = entities.count('ORG')
        features['date_entities'] = entities.count('DATE')
        
        # Scam keyword detection
        scam_keyword_count = 0
        for keyword in self.scam_keywords:
            if keyword in text.lower():
                scam_keyword_count += 1
        features['scam_keyword_count'] = scam_keyword_count
        features['scam_keyword_ratio'] = scam_keyword_count / max(features['word_count'], 1)
        
        # Capitalization ratio (potential spam indicator)
        caps_count = sum(1 for c in text if c.isupper())
        features['caps_ratio'] = caps_count / max(len(text), 1)
        
        # Punctuation count
        punct_count = sum(1 for c in text if c in '!?.,;:')
        features['punct_ratio'] = punct_count / max(len(text), 1)
        
        return features

    def detect_fake_news(self, text):
        """Main method for fake news detection"""
        # Preprocess text
        cleaned_text = self.preprocess_text(text)
        
        # Extract features
        features = self.extract_features(text)
        
        # Check for source if URL is present
        url_info = self.extract_url_info(text)
        
        # Use ML model if available
        ml_confidence = 0.5
        if self.news_model and self.vectorizer:
            try:
                # Vectorize text
                text_vectorized = self.vectorizer.transform([cleaned_text])
                ml_prediction = self.news_model.predict_proba(text_vectorized)[0]
                ml_confidence = ml_prediction[1]  # Probability of being fake
            except:
                ml_confidence = 0.5
        
        # Heuristic analysis
        heuristic_score = self.heuristic_analysis(text, features, url_info)
        
        # Combine scores
        final_score = (ml_confidence * 0.4 + heuristic_score * 0.6)
        
        # Determine verdict
        if final_score < 0.3:
            verdict = 'real'
            confidence = 1 - final_score
        elif final_score < 0.6:
            verdict = 'suspicious'
            confidence = 0.5 + abs(final_score - 0.45)
        else:
            verdict = 'fake'
            confidence = final_score
        
        # Detailed analysis
        details = {
            'ml_confidence': float(ml_confidence),
            'heuristic_score': float(heuristic_score),
            'features': features,
            'url_analysis': url_info,
            'reasons': self.get_reasons(text, features, url_info, verdict)
        }
        
        return {
            'verdict': verdict,
            'confidence': float(min(confidence, 1.0)),
            'details': details
        }

    def detect_scam(self, text):
        """Detect if message is a scam"""
        # Preprocess text
        cleaned_text = self.preprocess_text(text)
        
        # Extract features
        features = self.extract_features(text)
        
        # Use ML model if available
        ml_confidence = 0.5
        if self.scam_model and self.vectorizer:
            try:
                text_vectorized = self.vectorizer.transform([cleaned_text])
                ml_prediction = self.scam_model.predict_proba(text_vectorized)[0]
                ml_confidence = ml_prediction[1]
            except:
                ml_confidence = 0.5
        
        # Specialized scam detection
        scam_score = self.scam_heuristics(text, features)
        
        # Combine scores
        final_score = (ml_confidence * 0.3 + scam_score * 0.7)
        
        # Determine verdict
        if final_score < 0.3:
            verdict = 'real'
            confidence = 1 - final_score
        elif final_score < 0.6:
            verdict = 'suspicious'
            confidence = 0.5 + abs(final_score - 0.45)
        else:
            verdict = 'fake'
            confidence = final_score
        
        # Scam type identification
        scam_type = self.identify_scam_type(text)
        
        details = {
            'ml_confidence': float(ml_confidence),
            'scam_score': float(scam_score),
            'features': features,
            'scam_type': scam_type,
            'reasons': self.get_scam_reasons(text, features, scam_type)
        }
        
        return {
            'verdict': verdict,
            'confidence': float(min(confidence, 1.0)),
            'details': details
        }

    def heuristic_analysis(self, text, features, url_info):
        """Heuristic-based analysis for fake news"""
        score = 0.0
        reasons = []
        
        # Check for sensational language
        sensational_words = ['shocking', 'unbelievable', 'mind-blowing', 'you won\'t believe', 'viral']
        for word in sensational_words:
            if word in text.lower():
                score += 0.1
                break
        
        # Check for all-caps words (clickbait)
        words = text.split()
        caps_words = sum(1 for w in words if w.isupper() and len(w) > 2)
        if caps_words > 2:
            score += 0.1
        
        # Check for excessive punctuation
        if '!!!' in text or '???' in text:
            score += 0.1
        
        # Check for source credibility
        if url_info.get('domain'):
            domain = url_info['domain']
            if any(source in domain for source in self.trusted_sources):
                score -= 0.3
            elif any(satire in domain for satire in self.satire_sites):
                score += 0.4
            elif url_info.get('is_shortened'):
                score += 0.2
        
        # Check for lack of credible sources
        if 'according to' not in text.lower() and 'sources say' not in text.lower():
            score += 0.1
        
        # Emotional language analysis
        if features['sentiment_polarity'] > 0.5 or features['sentiment_polarity'] < -0.5:
            score += 0.1
        
        return min(score, 1.0)

    def scam_heuristics(self, text, features):
        """Specialized heuristics for scam detection"""
        score = 0.0
        
        # Check for urgency
        urgency_words = ['urgent', 'immediately', 'asap', 'limited time', 'act now', 'today only']
        for word in urgency_words:
            if word in text.lower():
                score += 0.15
                break
        
        # Check for money-related terms
        money_words = ['money', 'cash', 'prize', 'lottery', 'won', 'winner', 'inheritance']
        for word in money_words:
            if word in text.lower():
                score += 0.1
                break
        
        # Check for personal information requests
        info_words = ['ssn', 'social security', 'credit card', 'bank account', 'password']
        for word in info_words:
            if word in text.lower():
                score += 0.2
                break
        
        # Check for grammar issues (common in scams)
        blob = TextBlob(text)
        if blob.sentiment.polarity > 0.8:  # Overly positive
            score += 0.1
        
        # Check for scam keywords
        keyword_score = features['scam_keyword_ratio'] * 2
        score += keyword_score
        
        return min(score, 1.0)

    def identify_scam_type(self, text):
        """Identify the type of scam"""
        text_lower = text.lower()
        
        if any(word in text_lower for word in ['lottery', 'prize', 'won', 'winner']):
            return 'lottery_scam'
        elif any(word in text_lower for word in ['bank', 'account', 'verify', 'credit card']):
            return 'phishing_scam'
        elif any(word in text_lower for word in ['investment', 'bitcoin', 'crypto', 'profit']):
            return 'investment_scam'
        elif any(word in text_lower for word in ['romance', 'love', 'dating', 'single']):
            return 'romance_scam'
        elif any(word in text_lower for word in ['inheritance', 'lawyer', 'diaspora']):
            return 'advance_fee_scam'
        elif any(word in text_lower for word in ['tech support', 'microsoft', 'virus']):
            return 'tech_support_scam'
        else:
            return 'general_scam'

    def extract_url_info(self, text):
        """Extract and analyze URLs from text"""
        url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
        urls = re.findall(url_pattern, text)
        
        if not urls:
            return None
        
        url_info = {
            'urls': urls,
            'domain': None,
            'is_shortened': False,
            'article_content': None
        }
        
        # Check first URL
        url = urls[0]
        
        # Extract domain
        domain_match = re.search(r'https?://(?:www\.)?([^/]+)', url)
        if domain_match:
            url_info['domain'] = domain_match.group(1)
        
        # Check if shortened URL
        shortening_services = ['bit.ly', 'tinyurl', 'goo.gl', 'ow.ly', 'is.gd']
        if any(service in url for service in shortening_services):
            url_info['is_shortened'] = True
        
        # Try to extract article content
        try:
            article = Article(url)
            article.download()
            article.parse()
            url_info['article_content'] = article.text[:500]  # First 500 chars
        except:
            pass
        
        return url_info

    def get_reasons(self, text, features, url_info, verdict):
        """Generate reasons for the verdict"""
        reasons = []
        
        if verdict == 'fake':
            if url_info and url_info.get('domain'):
                if any(satire in url_info['domain'] for satire in self.satire_sites):
                    reasons.append("This appears to be from a known satire website")
                else:
                    reasons.append("The source domain has low credibility")
            
            if features['scam_keyword_count'] > 2:
                reasons.append("Contains multiple scam-related keywords")
            
            if '!!!' in text or '???' in text:
                reasons.append("Uses excessive punctuation typical of clickbait")
            
            if features['caps_ratio'] > 0.3:
                reasons.append("Unusual amount of capital letters")
        
        elif verdict == 'suspicious':
            reasons.append("Some elements of the message raise concerns")
            if features['sentiment_polarity'] > 0.7:
                reasons.append("The message is unusually positive/emotional")
        
        elif verdict == 'real':
            if url_info and url_info.get('domain'):
                if any(source in url_info['domain'] for source in self.trusted_sources):
                    reasons.append("Source is a trusted news organization")
            reasons.append("The message appears legitimate based on our analysis")
        
        return reasons

    def get_scam_reasons(self, text, features, scam_type):
        """Generate reasons for scam verdict"""
        reasons = []
        
        if scam_type == 'lottery_scam':
            reasons.append("This appears to be a lottery or prize scam")
            reasons.append("Legitimate lotteries don't ask for money to release prizes")
        
        elif scam_type == 'phishing_scam':
            reasons.append("This appears to be a phishing attempt")
            reasons.append("Legitimate companies don't ask for sensitive info via text")
        
        elif scam_type == 'investment_scam':
            reasons.append("This appears to be an investment scam")
            reasons.append("Be wary of unsolicited investment opportunities")
        
        elif scam_type == 'romance_scam':
            reasons.append("This appears to be a romance scam")
            reasons.append("Be cautious with online relationships asking for money")
        
        elif scam_type == 'advance_fee_scam':
            reasons.append("This appears to be an advance fee scam")
            reasons.append("Never pay money to receive money")
        
        elif scam_type == 'tech_support_scam':
            reasons.append("This appears to be a tech support scam")
            reasons.append("Legitimate companies don't contact you unsolicited")
        
        if features['scam_keyword_count'] > 0:
            reasons.append(f"Contains {features['scam_keyword_count']} scam-related keywords")
        
        return reasons

    def analyze_url_safety(self, url):
        """Analyze URL for potential threats"""
        # This would integrate with Google Safe Browsing API or similar
        # For now, return basic analysis
        return {
            'safe': True,
            'threats': []
        }