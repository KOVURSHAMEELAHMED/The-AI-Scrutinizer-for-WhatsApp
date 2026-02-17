import logging

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db import DatabaseError

from twilio.twiml.messaging_response import MessagingResponse

from .services.message_handler import MessageHandler
from .models import User, Message, AnalysisResult


logger = logging.getLogger(__name__)
message_handler = MessageHandler()


# =====================================================
# WhatsApp Webhook Endpoint (Twilio)
# =====================================================

@csrf_exempt
def webhook(request):
    """
    Twilio WhatsApp webhook endpoint.
    Handles incoming messages.
    """

    if request.method != "POST":
        return HttpResponse("Method not allowed", status=405)

    try:
        # Extract Twilio payload
        from_number = request.POST.get("From", "")
        message_body = request.POST.get("Body", "").strip()
        media_url = request.POST.get("MediaUrl0")

        if not from_number:
            logger.warning("Webhook received without sender number.")
            return HttpResponse("Invalid request", status=400)

        # Remove 'whatsapp:' prefix if present
        from_number = from_number.replace("whatsapp:", "")

        logger.info(
            f"Incoming message | From: {from_number} | "
            f"Text preview: {message_body[:50]}"
        )

        # Process using AI handler
        success = message_handler.process_incoming_message(
            from_number=from_number,
            message_body=message_body,
            media_url=media_url,
        )

        # Twilio requires valid TwiML response
        response = MessagingResponse()

        if success:
            # Optional: Immediate acknowledgment
            # response.message("Your message is being analyzed...")
            return HttpResponse(str(response), content_type="text/xml")

        else:
            logger.error("Message processing failed.")
            response.message("Sorry, something went wrong. Please try again.")
            return HttpResponse(str(response), content_type="text/xml")

    except Exception as e:
        logger.exception(f"Critical webhook error: {str(e)}")

        response = MessagingResponse()
        response.message("Server error. Please try again later.")
        return HttpResponse(str(response), content_type="text/xml")


# =====================================================
# Health Check Endpoint
# =====================================================

def health_check(request):
    """
    Health endpoint for monitoring.
    """

    return JsonResponse({
        "status": "healthy",
        "timestamp": timezone.now().isoformat(),
    })


# =====================================================
# System Statistics Endpoint
# =====================================================

def stats(request):
    """
    Returns system usage statistics.
    """

    try:
        today = timezone.now().date()

        data = {
            "total_users": User.objects.count(),
            "active_today": User.objects.filter(
                last_active__date=today
            ).count(),
            "total_messages": Message.objects.count(),
            "total_analyses": AnalysisResult.objects.count(),
        }

        return JsonResponse(data)

    except DatabaseError as db_error:
        logger.error(f"Database error in stats endpoint: {str(db_error)}")
        return JsonResponse({"error": "Database error"}, status=500)

    except Exception as e:
        logger.exception(f"Unexpected stats error: {str(e)}")
        return JsonResponse({"error": "Server error"}, status=500)
