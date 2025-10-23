from unittest import result
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import BackupUML
from .services import call_gemini
import json
import re
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser
import base64
from .services import call_gemini_from_image


class GenerateUMLView(APIView):
    def post(self, request):
        prompt = request.data.get("prompt")
        if not prompt:
            return Response({"error": "El campo 'prompt' es requerido"}, status=status.HTTP_400_BAD_REQUEST)

        output = call_gemini(prompt)

        # 🧹 Limpiar bloque de código Markdown si viene envuelto en ```json ... ```
        if isinstance(output, str):
            output = re.sub(r"^```json\s*|\s*```$", "",
                            output.strip(), flags=re.MULTILINE)

        try:
            parsed_json = json.loads(output)
        except Exception as e:
            return Response({
                "error": "Gemini devolvió un formato inválido",
                "raw": output,
                "exception": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(parsed_json, status=status.HTTP_200_OK)


@api_view(['POST'])
def set_backupUML(request, room_id):
    if not room_id:
        return Response({"error": "Se requiere el campo 'room_id'"}, status=status.HTTP_400_BAD_REQUEST)

    data = request.data

    try:
        # Buscar si ya existe
        uml_backup, created = BackupUML.objects.update_or_create(
            room_id=room_id,
            defaults={"data": data}
        )
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    return Response({
        "message": "UML creado con éxito" if created else "UML actualizado con éxito",
        "room_id": str(uml_backup.room_id),
        "data": uml_backup.data
    }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


@api_view(['GET'])
def get_backupUML(request, room_id):
    if not room_id:
        return Response({"error": "Se requiere el campo 'room_id'"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        diagrama = BackupUML.objects.get(room_id=room_id)
    except BackupUML.DoesNotExist:
        return Response({"error": "No existe un diagrama con ese ID"}, status=status.HTTP_404_NOT_FOUND)

    # ✅ Devolver el JSON guardado exactamente como está en la BD
    return Response(diagrama.data, status=status.HTTP_200_OK)


@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser])
def analyze_uml_image(request):
    """
    Espera un archivo de imagen (PNG o JPG).
    """
    image_file = request.FILES.get("image")

    if not image_file:
        return Response({"error": "Debe enviar un archivo 'image'"}, status=status.HTTP_400_BAD_REQUEST)

    # Convertir a Base64
    image_base64 = base64.b64encode(image_file.read()).decode("utf-8")

    # Llamar al servicio Gemini
    result = call_gemini_from_image(
        image_base64, mime_type=image_file.content_type
    )

    # Intentar parsear el resultado JSON
    try:
        parsed = json.loads(result) if isinstance(result, str) else result
    except Exception:
        parsed = {"raw": result, "error": "No se pudo parsear correctamente"}

    return Response({"uml_json": parsed}, status=status.HTTP_200_OK)
