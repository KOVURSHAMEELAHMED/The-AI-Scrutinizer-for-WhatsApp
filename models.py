from django.db import models
from django.utils import timezone
import json

class User(models.Model):
    """Store user information"""
    phone_number = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100, blank=True, null=True)
    language = models.CharField(max_length=10, default='en')
    created_at = models.DateTimeField(default=timezone.now)
    last_active = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=True)
    total_queries = models.IntegerField(default=0)
    
    class Meta:
        indexes = [
            models.Index(fields=['phone_number']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.phone_number} - {self.name or 'Unknown'}"

class Message(models.Model):
    """Store all incoming and outgoing messages"""
    MESSAGE_TYPES = [
        ('incoming', 'Incoming'),
        ('outgoing', 'Outgoing'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='messages')
    message_type = models.CharField(max_length=10, choices=MESSAGE_TYPES)
    content = models.TextField()
    media_url = models.URLField(blank=True, null=True)
    timestamp = models.DateTimeField(default=timezone.now)
    processed = models.BooleanField(default=False)
    
    class Meta:
        indexes = [
            models.Index(fields=['user', '-timestamp']),
        ]

class AnalysisResult(models.Model):
    """Store analysis results for messages"""
    ANALYSIS_TYPES = [
        ('news', 'Fake News Detection'),
        ('scam', 'Scam Detection'),
        ('fact_check', 'Fact Check'),
        ('url', 'URL Analysis'),
    ]
    
    VERDICT_CHOICES = [
        ('real', 'Real/Legitimate'),
        ('fake', 'Fake/Scam'),
        ('suspicious', 'Suspicious'),
        ('unverified', 'Unverified'),
    ]
    
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='analyses')
    analysis_type = models.CharField(max_length=20, choices=ANALYSIS_TYPES)
    verdict = models.CharField(max_length=20, choices=VERDICT_CHOICES)
    confidence_score = models.FloatField()
    details = models.JSONField(default=dict)
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        indexes = [
            models.Index(fields=['message', 'analysis_type']),
            models.Index(fields=['-created_at']),
        ]

class URLScan(models.Model):
    """Store URL scanning results"""
    url = models.URLField()
    domain = models.CharField(max_length=255)
    is_malicious = models.BooleanField(default=False)
    threat_type = models.CharField(max_length=100, blank=True)
    scan_details = models.JSONField(default=dict)
    created_at = models.DateTimeField(default=timezone.now)
    analysis = models.ForeignKey(AnalysisResult, on_delete=models.CASCADE, related_name='url_scans', null=True)

class TrainingData(models.Model):
    """Store training data for model improvement"""
    original_message = models.TextField()
    user_verdict = models.CharField(max_length=20, choices=AnalysisResult.VERDICT_CHOICES)
    ai_verdict = models.CharField(max_length=20, choices=AnalysisResult.VERDICT_CHOICES)
    user_feedback = models.TextField(blank=True)
    used_for_training = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)