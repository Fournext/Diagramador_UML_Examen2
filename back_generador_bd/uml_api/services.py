import requests
from django.conf import settings

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

def call_gemini(prompt: str):
    GEMINI_API_KEY = getattr(settings, "GEMINI_API_KEY", None)

    headers = {"Content-Type": "application/json"}
    params = {"key": GEMINI_API_KEY}

    # Detectar si es una solicitud de edición
    edit_keywords = ["cambies","cambiar", "cambia"
                     "edites","edita","editar", 
                     "modifiques", "modifica","modificar", 
                     "actualices", "actualizar","actualiza"
                    ]
    is_edit_request = any(keyword in prompt.lower() for keyword in edit_keywords)

    if is_edit_request:
        # Prompt para edición - devolver dos JSONs
        prompt_text = f"""
Analiza el siguiente prompt de edición y devuelve DOS JSONs separados:

IMPORTANTE: El usuario quiere editar/modificar una tabla existente. Debes devolver:

1. **JSON ORIGINAL**: El modelo UML completo como está actualmente (sin cambios)
2. **JSON EDITADO**: Solo los elementos modificados con el atributo "editado": true

Formato de respuesta:
```json
{{
  "original": {{
    "classes": [
      {{
        "id": "uuid",
        "name": "NombreClase",
        "attributes": [
          {{"name": "atributo", "type": "tipo"}}
        ],
        "methods": [
          {{"name": "metodo", "parameters": "", "returnType": ""}}
        ]
      }}
    ],
    "relationships": [
      {{
        "id": "uuid",
        "type": "association | generalization | aggregation | composition | dependency",
        "sourceId": "uuid",
        "targetId": "uuid",
        "labels": ["1..*", "1"]
      }}
    ]
  }},
  "editado": {{
    "classes": [
      {{
        "id": "mismo_uuid_del_original",
        "name": "NombreClaseModificado",
        "attributes": [
          {{"name": "atributo_modificado", "type": "tipo", "editado": true}}
        ],
        "methods": [
          {{"name": "metodo_modificado", "parameters": "", "returnType": "", "editado": true}}
        ],
        "editado": true
      }}
    ],
    "relationships": []
  }}
}}
```

Usa los mismos UUIDs en ambos JSONs para la misma entidad.
Solo incluye en "editado" los elementos que realmente cambiaron.
NO devuelvas nada más, solo el JSON.

Prompt del usuario:
{prompt}
"""
    else:
        # Prompt normal - devolver un solo JSON
        prompt_text = f"""
Convierte el siguiente prompt en un JSON UML válido. 
El JSON **debe seguir exactamente** esta estructura:

{{
  "classes": [
    {{
      "id": "uuid",
      "name": "NombreClase",
      "attributes": [
        {{"name": "atributo", "type": "tipo"}}
      ],
      "methods": [
        {{"name": "metodo", "parameters": "", "returnType": ""}}
      ]
    }}
  ],
  "relationships": [
    {{
      "id": "uuid",
      "type": "association | generalization | aggregation | composition | dependency",
      "sourceId": "uuid",
      "targetId": "uuid",
      "labels": ["1..*", "1"]
    }}
  ]
}}

Usa UUIDs generados aleatoriamente como 'id'.
NO devuelvas nada más, solo el JSON.

Prompt del usuario:
{prompt}
"""

    data = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt_text
                    }
                ]
            }
        ]
    }

    response = requests.post(GEMINI_API_URL, headers=headers, params=params, json=data)
    response.raise_for_status()
    result = response.json()

    try:
        text_output = result['candidates'][0]['content']['parts'][0]['text']
        return text_output
    except (KeyError, IndexError):
        return '{"error": "No se pudo parsear la respuesta de Gemini"}'

def call_gemini_analysis(prompt: str):
    GEMINI_API_KEY = getattr(settings, "GEMINI_API_KEY", None)

    headers = {"Content-Type": "application/json"}
    params = {"key": GEMINI_API_KEY}

    data = {
        "contents": [
            {
                "parts": [
                    {
                        "text": f"""
Analiza este modelo UML y responde SOLO en formato JSON.

Estructura de salida obligatoria:
{{
  "validas": [
    {{
      "relacion": "Texto corto con tipo y tablas",
      "razon": "Por qué es válida"
    }}
  ],
  "errores": [
    {{
      "relacion": "Texto corto con tipo y tablas",
      "problema": "Qué está mal",
      "sugerencia": "Cómo corregirlo"
    }}
  ]
}}

No escribas explicaciones fuera del JSON.
Prompt:
{prompt}
"""
                    }
                ]
            }
        ]
    }

    response = requests.post(GEMINI_API_URL, headers=headers, params=params, json=data)
    response.raise_for_status()
    result = response.json()

    try:
        text_output = result["candidates"][0]["content"]["parts"][0]["text"]
        return text_output
    except (KeyError, IndexError):
        return '{"error": "No se pudo parsear la respuesta de Gemini"}'

def call_gemini_edit(original_model: str, edit_prompt: str):
    """
    Función específica para editar un modelo UML existente.
    Recibe el modelo original y el prompt de edición.
    """
    GEMINI_API_KEY = getattr(settings, "GEMINI_API_KEY", None)

    headers = {"Content-Type": "application/json"}
    params = {"key": GEMINI_API_KEY}

    data = {
        "contents": [
            {
                "parts": [
                    {
                        "text": f"""
Tienes un modelo UML existente y una solicitud de edición. Devuelve DOS JSONs:

MODELO ORIGINAL:
{original_model}

SOLICITUD DE EDICIÓN:
{edit_prompt}

Formato de respuesta exacto:
{{
  "original": {original_model},
  "editado": {{
    "classes": [
      {{
        "id": "mismo_uuid_del_original",
        "name": "NombreModificado",
        "attributes": [
          {{"name": "nombre_modificado", "type": "tipo", "editado": true}}
        ],
        "methods": [
          {{"name": "metodo_modificado", "parameters": "", "returnType": "", "editado": true}}
        ],
        "editado": true
      }}
    ],
    "relationships": [
      // Solo si se modifican relaciones
    ]
  }}
}}

REGLAS:
1. Mantén los mismos UUIDs en ambos JSONs
2. En "editado" solo incluye los elementos que cambiaron
3. Marca con "editado": true los elementos modificados
4. NO devuelvas nada más que el JSON
"""
                    }
                ]
            }
        ]
    }

    response = requests.post(GEMINI_API_URL, headers=headers, params=params, json=data)
    response.raise_for_status()
    result = response.json()

    try:
        text_output = result["candidates"][0]["content"]["parts"][0]["text"]
        return text_output
    except (KeyError, IndexError):
        return '{"error": "No se pudo parsear la respuesta de Gemini"}'
