import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .services.message_handler import detect_scam
from .models import MessageLog


def health_check(request):
    return JsonResponse({"status": "OK"})


@csrf_exempt
def analyze_message(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST method required"}, status=400)

    try:
        body = json.loads(request.body)
        text = body.get("text")

        if not text:
            return JsonResponse({"error": "Text is required"}, status=400)

        prediction, confidence = detect_scam(text)

        MessageLog.objects.create(
            text=text,
            prediction=prediction,
            confidence=confidence,
        )

        return JsonResponse({
            "prediction": prediction,
            "confidence": confidence
        })

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

