import re
from twilio.rest import Client
from django.conf import settings
from ..models import User, Message, AnalysisResult
from .nlp_detector import NLPDetector
from .fact_checker import FactChecker
import logging
from datetime import datetime
import hashlib

logger = logging.getLogger(__name__)

class MessageHandler:
    def __init__(self):
        self.twilio_client = Client(
            settings.TWILIO_ACCOUNT_SID,
            settings.TWILIO_AUTH_TOKEN
        )
        self.nlp_detector = NLPDetector()
        self.fact_checker = FactChecker()
        
        # Command patterns
        self.commands = {
            r'^/start$': self.handle_start,
            r'^/help$': self.handle_help,
            r'^/check\s+(.+)$': self.handle_check,
            r'^/news\s+(.+)$': self.handle_news_check,
            r'^/scam\s+(.+)$': self.handle_scam_check,
            r'^/fact\s+(.+)$': self.handle_fact_check,
            r'^/feedback\s+(.+)$': self.handle_feedback,
            r'^/stats$': self.handle_stats,
        }

    def process_incoming_message(self, from_number, message_body, media_url=None):
        """Main entry point for processing incoming WhatsApp messages"""
        try:
            # Get or create user
            user, created = User.objects.get_or_create(
                phone_number=from_number,
                defaults={'last_active': datetime.now()}
            )
            
            # Update user stats
            user.last_active = datetime.now()
            user.total_queries += 1
            user.save()
            
            # Save incoming message
            incoming_msg = Message.objects.create(
                user=user,
                message_type='incoming',
                content=message_body,
                media_url=media_url
            )
            
            # Process message and generate response
            response_text = self.generate_response(user, message_body, media_url)
            
            # Save outgoing message
            outgoing_msg = Message.objects.create(
                user=user,
                message_type='outgoing',
                content=response_text
            )
            
            # Send response via Twilio
            self.send_whatsapp_message(from_number, response_text)
            
            return True
            
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            self.send_whatsapp_message(
                from_number,
                "Sorry, I encountered an error. Please try again later."
            )
            return False

    def generate_response(self, user, message, media_url=None):
        """Generate appropriate response based on message content"""
        # Check for commands
        for pattern, handler in self.commands.items():
            match = re.match(pattern, message.strip(), re.IGNORECASE)
            if match:
                return handler(user, *match.groups())
        
        # If no command matched, perform automatic detection
        return self.auto_detect(user, message, media_url)

    def handle_start(self, user, *args):
        """Handle /start command"""
        return (
            "👋 Welcome to the Fake News & Scam Detector Bot!\n\n"
            "I can help you identify fake news, scams, and verify information.\n\n"
            "Available commands:\n"
            "/help - Show this help message\n"
            "/check [text] - Analyze any text\n"
            "/news [text] - Check for fake news\n"
            "/scam [text] - Check for scams\n"
            "/fact [claim] - Fact check a claim\n"
            "/stats - View your usage statistics\n"
            "/feedback [text] - Provide feedback\n\n"
            "Just send me any message and I'll analyze it automatically!"
        )

    def handle_help(self, user, *args):
        """Handle /help command"""
        return self.handle_start(user)

    def handle_check(self, user, text):
        """Handle /check command - general analysis"""
        # Analyze for both fake news and scams
        news_result = self.nlp_detector.detect_fake_news(text)
        scam_result = self.nlp_detector.detect_scam(text)
        
        # Save analysis results
        message = Message.objects.filter(user=user, message_type='incoming').latest('timestamp')
        
        AnalysisResult.objects.create(
            message=message,
            analysis_type='news',
            verdict=news_result['verdict'],
            confidence_score=news_result['confidence'],
            details=news_result['details']
        )
        
        AnalysisResult.objects.create(
            message=message,
            analysis_type='scam',
            verdict=scam_result['verdict'],
            confidence_score=scam_result['confidence'],
            details=scam_result['details']
        )
        
        # Format response
        response = "📊 *Analysis Results*\n\n"
        
        # Fake news result
        news_emoji = self.get_verdict_emoji(news_result['verdict'])
        response += f"{news_emoji} *Fake News Detection:*\n"
        response += f"Verdict: {news_result['verdict'].upper()}\n"
        response += f"Confidence: {news_result['confidence']:.1%}\n\n"
        
        # Scam detection result
        scam_emoji = self.get_verdict_emoji(scam_result['verdict'])
        response += f"{scam_emoji} *Scam Detection:*\n"
        response += f"Verdict: {scam_result['verdict'].upper()}\n"
        response += f"Confidence: {scam_result['confidence']:.1%}\n\n"
        
        # Add reasons
        response += "*Key Findings:*\n"
        all_reasons = (news_result['details'].get('reasons', []) + 
                      scam_result['details'].get('reasons', []))
        for reason in all_reasons[:3]:  # Show top 3 reasons
            response += f"• {reason}\n"
        
        response += "\n*Tips:*\n"
        response += "• Verify information from multiple sources\n"
        response += "• Be cautious with unsolicited messages\n"
        response += "• Use /fact for specific claims"
        
        return response

    def handle_news_check(self, user, text):
        """Handle /news command - fake news detection only"""
        result = self.nlp_detector.detect_fake_news(text)
        
        # Save analysis
        message = Message.objects.filter(user=user, message_type='incoming').latest('timestamp')
        AnalysisResult.objects.create(
            message=message,
            analysis_type='news',
            verdict=result['verdict'],
            confidence_score=result['confidence'],
            details=result['details']
        )
        
        # Format response
        emoji = self.get_verdict_emoji(result['verdict'])
        response = f"{emoji} *Fake News Analysis*\n\n"
        response += f"Verdict: {result['verdict'].upper()}\n"
        response += f"Confidence: {result['confidence']:.1%}\n\n"
        
        if result['details'].get('reasons'):
            response += "*Reasons:*\n"
            for reason in result['details']['reasons']:
                response += f"• {reason}\n"
        
        return response

    def handle_scam_check(self, user, text):
        """Handle /scam command - scam detection only"""
        result = self.nlp_detector.detect_scam(text)
        
        # Save analysis
        message = Message.objects.filter(user=user, message_type='incoming').latest('timestamp')
        AnalysisResult.objects.create(
            message=message,
            analysis_type='scam',
            verdict=result['verdict'],
            confidence_score=result['confidence'],
            details=result['details']
        )
        
        # Format response
        emoji = self.get_verdict_emoji(result['verdict'])
        response = f"{emoji} *Scam Detection Analysis*\n\n"
        response += f"Verdict: {result['verdict'].upper()}\n"
        response += f"Confidence: {result['confidence']:.1%}\n\n"
        
        if result['details'].get('scam_type'):
            scam_type = result['details']['scam_type'].replace('_', ' ').title()
            response += f"Potential Scam Type: {scam_type}\n\n"
        
        if result['details'].get('reasons'):
            response += "*Warning Signs:*\n"
            for reason in result['details']['reasons']:
                response += f"⚠️ {reason}\n"
        
        return response

    def handle_fact_check(self, user, claim):
        """Handle /fact command - fact checking"""
        result = self.fact_checker.check_claim(claim)
        
        # Format response
        response = "🔍 *Fact Check Results*\n\n"
        response += f"Claim: \"{claim[:100]}{'...' if len(claim) > 100 else ''}\"\n\n"
        
        if result['sources']:
            response += f"Status: {result['status']}\n"
            response += f"Confidence: {result['confidence']:.1%}\n\n"
            response += "*Sources:*\n"
            for source in result['sources'][:3]:
                response += f"• {source['title']}: {source['url']}\n"
        else:
            response += "No fact-checking sources found for this claim.\n"
            response += "Try rephrasing or check reputable news sources."
        
        return response

    def handle_feedback(self, user, feedback):
        """Handle /feedback command"""
        # Save feedback for model improvement
        message = Message.objects.filter(user=user, message_type='incoming').latest('timestamp')
        
        # Create training data entry
        from ..models import TrainingData
        TrainingData.objects.create(
            original_message=message.content,
            user_verdict='unverified',
            ai_verdict='unverified',
            user_feedback=feedback
        )
        
        return (
            "✅ Thank you for your feedback!\n"
            "Your input helps us improve our detection accuracy."
        )

    def handle_stats(self, user, *args):
        """Handle /stats command"""
        total_messages = Message.objects.filter(user=user).count()
        incoming = Message.objects.filter(user=user, message_type='incoming').count()
        analyses = AnalysisResult.objects.filter(message__user=user).count()
        
        # Get recent verdicts
        recent_analyses = AnalysisResult.objects.filter(
            message__user=user
        ).order_by('-created_at')[:10]
        
        fake_count = sum(1 for a in recent_analyses if a.verdict == 'fake')
        real_count = sum(1 for a in recent_analyses if a.verdict == 'real')
        suspicious_count = sum(1 for a in recent_analyses if a.verdict == 'suspicious')
        
        response = "📈 *Your Statistics*\n\n"
        response += f"Total Messages: {total_messages}\n"
        response += f"Messages Analyzed: {incoming}\n"
        response += f"Total Analyses: {analyses}\n\n"
        response += "*Recent Activity (last 10 analyses):*\n"
        response += f"✓ Real: {real_count}\n"
        response += f"⚠️ Suspicious: {suspicious_count}\n"
        response += f"✗ Fake/Scam: {fake_count}\n\n"
        response += f"Member since: {user.created_at.strftime('%B %d, %Y')}"
        
        return response

    def auto_detect(self, user, message, media_url=None):
        """Automatic detection for non-command messages"""
        # Perform comprehensive analysis
        result = self.nlp_detector.detect_fake_news(message)
        scam_result = self.nlp_detector.detect_scam(message)
        
        # Save analyses
        msg = Message.objects.filter(user=user, message_type='incoming').latest('timestamp')
        
        AnalysisResult.objects.create(
            message=msg,
            analysis_type='news',
            verdict=result['verdict'],
            confidence_score=result['confidence'],
            details=result['details']
        )
        
        AnalysisResult.objects.create(
            message=msg,
            analysis_type='scam',
            verdict=scam_result['verdict'],
            confidence_score=scam_result['confidence'],
            details=scam_result['details']
        )
        
        # Generate appropriate response based on severity
        if scam_result['verdict'] == 'fake' and scam_result['confidence'] > 0.7:
            return self.format_scam_alert(scam_result)
        elif result['verdict'] == 'fake' and result['confidence'] > 0.7:
            return self.format_fake_news_alert(result)
        elif scam_result['verdict'] == 'suspicious' or result['verdict'] == 'suspicious':
            return self.format_suspicious_alert(result, scam_result)
        else:
            return self.format_safe_message(result, scam_result)

    def format_scam_alert(self, scam_result):
        """Format scam alert message"""
        response = "🚨 *HIGH CONFIDENCE SCAM DETECTED*\n\n"
        response += "⚠️ This message shows multiple scam indicators:\n"
        
        for reason in scam_result['details'].get('reasons', []):
            response += f"• {reason}\n"
        
        response += "\n*What to do:*\n"
        response += "• Do NOT reply or click any links\n"
        response += "• Do NOT share personal information\n"
        response += "• Block and report the sender\n"
        response += "• Forward suspicious messages to 7726 (SPAM)\n\n"
        response += "Stay safe! 🛡️"
        
        return response

    def format_fake_news_alert(self, news_result):
        """Format fake news alert message"""
        response = "📰 *POTENTIAL FAKE NEWS DETECTED*\n\n"
        response += f"Confidence: {news_result['confidence']:.1%}\n\n"
        response += "*Why this may be fake:*\n"
        
        for reason in news_result['details'].get('reasons', []):
            response += f"• {reason}\n"
        
        response += "\n*Tips for verification:*\n"
        response += "• Check trusted news sources\n"
        response += "• Look for the original source\n"
        response += "• Check publication dates\n"
        response += "• Be wary of sensational headlines\n\n"
        response += "Always verify before sharing! ✅"
        
        return response

    def format_suspicious_alert(self, news_result, scam_result):
        """Format suspicious message alert"""
        response = "⚠️ *SUSPICIOUS CONTENT DETECTED*\n\n"
        response += "This message has some concerning elements:\n\n"
        
        if scam_result['confidence'] > 0.5:
            response += f"Scam likelihood: {scam_result['confidence']:.1%}\n"
            if scam_result['details'].get('reasons'):
                response += f"• {scam_result['details']['reasons'][0]}\n"
        
        if news_result['confidence'] > 0.5:
            response += f"Fake news likelihood: {news_result['confidence']:.1%}\n"
            if news_result['details'].get('reasons'):
                response += f"• {news_result['details']['reasons'][0]}\n"
        
        response += "\n*Recommendation:*\n"
        response += "Exercise caution with this message. Verify through trusted sources before acting on it."
        
        return response

    def format_safe_message(self, news_result, scam_result):
        """Format safe message response"""
        response = "✅ *MESSAGE APPEARS SAFE*\n\n"
        response += "Our analysis didn't find significant red flags:\n\n"
        response += f"Fake news confidence: {news_result['confidence']:.1%}\n"
        response += f"Scam confidence: {scam_result['confidence']:.1%}\n\n"
        response += "Remember to always:\n"
        response += "• Stay vigilant with unexpected messages\n"
        response += "• Verify important information\n"
        response += "• Report suspicious content\n\n"
        response += "Use /help for more commands!"
        
        return response

    def get_verdict_emoji(self, verdict):
        """Get appropriate emoji for verdict"""
        emojis = {
            'real': '✅',
            'fake': '❌',
            'suspicious': '⚠️',
            'unverified': '❓'
        }
        return emojis.get(verdict, 'ℹ️')

    def send_whatsapp_message(self, to_number, message):
        """Send message via Twilio WhatsApp"""
        try:
            self.twilio_client.messages.create(
                body=message,
                from_=f'whatsapp:{settings.TWILIO_WHATSAPP_NUMBER}',
                to=f'whatsapp:{to_number}'
            )
        except Exception as e:
            logger.error(f"Error sending WhatsApp message: {str(e)}")