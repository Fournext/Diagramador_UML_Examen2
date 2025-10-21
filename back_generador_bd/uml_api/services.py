import requests
from django.conf import settings

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

def call_gemini(prompt: str):
    GEMINI_API_KEY = getattr(settings, "GEMINI_API_KEY", None)

    headers = {"Content-Type": "application/json"}
    params = {"key": GEMINI_API_KEY}

    # Detectar si es una solicitud de edición
    edit_keywords = ["cambies","cambiar", "cambia",
                     "edites","edita","editar", 
                     "modifiques", "modifica","modificar", 
                     "actualices", "actualizar","actualiza",
                     "agregar", "agrega","añadir","añade"
                    ]
    is_edit_request = any(keyword in prompt.lower() for keyword in edit_keywords)

    if is_edit_request:
        # Prompt para edición - devolver dos JSONs
        prompt_text = f"""
Analiza el siguiente prompt de edición y devuelve DOS JSONs separados:

IMPORTANTE: El usuario quiere editar/modificar una tabla o relación existente. Debes devolver:

1. **JSON ORIGINAL**: El modelo UML completo como está actualmente (sin cambios)
2. **JSON EDITADO**: Solo los elementos modificados aplicando EXACTAMENTE los cambios solicitados

Ejemplo de cambio de atributo:
- Si el prompt dice "cambia fecha:Date a fecha_Hora:String"
- En "editado" debe aparecer: {{"name": "fecha_Hora", "type": "String", "editado": true}}

Formato de respuesta:
```json
{{
  "original": {{
    "classes": [
      {{
        "id": "uuid",
        "name": "NombreClase",
        "attributes": [
          {{"name": "atributo_original", "type": "tipo_original"}}
        ],
        "methods": [
          {{"name": "metodo_original", "parameters": "", "returnType": ""}}
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
        "id": "mismo_id_del_original",
        "name": "NombreClaseModificado",
        "attributes": [
          {{"name": "nuevo_nombre_atributo", "type": "nuevo_tipo", "editado": true}}
        ],
        "methods": [
          {{"name": "nuevo_nombre_metodo", "parameters": "nuevos_params", "returnType": "nuevo_tipo", "editado": true}}
        ],
        "editado": true
      }}
    ],
    "relationships": [
      {{
        "id": "mismo_id_del_original",
        "type": "nuevo_tipo_relacion",
        "sourceId": "uuid",
        "targetId": "uuid",
        "labels": ["nueva_etiqueta1", "nueva_etiqueta2"],
        "editado": true
      }}
    ]
  }}
}}
```

REGLAS CRÍTICAS:
- Aplica EXACTAMENTE los cambios solicitados en el prompt
- Si el prompt dice "cambia X a Y", en "editado" debe aparecer Y, NO X
- En "editado" solo incluye los elementos que REALMENTE cambiaron con sus NUEVOS valores
- Usa los mismos UUIDs en ambos JSONs para la misma entidad
- Marca con "editado": true SOLO los elementos que sufrieron modificaciones
- NO devuelvas nada más, solo el JSON

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

