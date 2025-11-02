import re
import requests
import json
from django.conf import settings

from uuid import uuid4

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"


def call_gemini(prompt: str):
    GEMINI_API_KEY = getattr(settings, "GEMINI_API_KEY", None)

    headers = {"Content-Type": "application/json"}
    params = {"key": GEMINI_API_KEY}

    # Detectar si es una solicitud de eliminación
    delete_keywords = ["eliminar", "elimina", "borra", "borrar", 
                      "quitar", "quita", "remover", "remueve",
                      "sacar", "saca", "delete", "remove"]
    is_delete_request = any(keyword in prompt.lower() for keyword in delete_keywords)

    # Detectar si es una solicitud de edición
    edit_keywords = ["cambies", "cambiar", "cambia",
                     "edites", "edita", "editar",
                     "modifiques", "modifica", "modificar",
                     "actualices", "actualizar", "actualiza",
                     "añadir", "añade"
                     ]
    is_edit_request = any(keyword in prompt.lower()
                          for keyword in edit_keywords)

    if is_delete_request:
        # Prompt para eliminación - devolver un solo JSON con marcadores de eliminación
        prompt_text = f"""
Analiza el siguiente prompt de eliminación y devuelve UN SOLO JSON con los elementos marcados para eliminar.

IMPORTANTE: El usuario quiere ELIMINAR elementos (clases, atributos, métodos o relaciones). Debes:

1. Identificar QUÉ se debe eliminar según el prompt
2. Marcar esos elementos con "eliminar": true
3. Devolver SOLO los elementos que se deben eliminar

Formato de respuesta:
```json
{{
  "classes": [
    {{
      "id": "uuid_o_nombre_clase",
      "name": "NombreClase",
      "eliminar": true,
      "attributes": [
        {{"name": "atributo_a_eliminar", "type": "tipo", "eliminar": true}}
      ],
      "methods": [
        {{"name": "metodo_a_eliminar", "parameters": "", "returnType": "", "eliminar": true}}
      ]
    }}
  ],
  "relationships": [
    {{
      "id": "uuid_relacion",
      "type": "association | generalization | aggregation | composition | dependency",
      "sourceId": "nombre_clase_origen",
      "targetId": "nombre_clase_destino",
      "eliminar": true
    }}
  ]
}}
```

REGLAS IMPORTANTES:
- Si se debe eliminar UNA CLASE COMPLETA, marca la clase con "eliminar": true y NO incluyas attributes/methods
- Si se debe eliminar UN ATRIBUTO específico, incluye solo ese atributo con "eliminar": true dentro de la clase
- Si se debe eliminar UN MÉTODO específico, incluye solo ese método con "eliminar": true dentro de la clase
- Si se debe eliminar UNA RELACIÓN, márcala con "eliminar": true e identifícala por sourceId/targetId (nombres de clases)
- Usa nombres de clases (no UUIDs) para sourceId y targetId en relaciones
- NO incluyas elementos que NO se deben eliminar
- NO devuelvas nada más, solo el JSON

Ejemplos:
- "elimina la clase Usuario" → {{"classes": [{{"name": "Usuario", "eliminar": true}}]}}
- "quita el atributo edad de Persona" → {{"classes": [{{"name": "Persona", "attributes": [{{"name": "edad", "eliminar": true}}]}}]}}
- "borra la relación entre Persona y Cliente" → {{"relationships": [{{"sourceId": "Persona", "targetId": "Cliente", "eliminar": true}}]}}

Prompt del usuario:
{prompt}
"""
    elif is_edit_request:
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

    response = requests.post(
        GEMINI_API_URL, headers=headers, params=params, json=data)
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

    response = requests.post(
        GEMINI_API_URL, headers=headers, params=params, json=data)
    response.raise_for_status()
    result = response.json()

    try:
        text_output = result["candidates"][0]["content"]["parts"][0]["text"]
        return text_output
    except (KeyError, IndexError):
        return '{"error": "No se pudo parsear la respuesta de Gemini"}'


# ===============================================================
# 🔹 Nuevo servicio: Procesar imagen UML → devolver JSON
# ===============================================================
# ===============================================================
# 🔹 Servicio: Procesar imagen UML → devolver JSON limpio y estructurado
# ===============================================================
def call_gemini_from_image(image_base64: str, mime_type: str = "image/png"):
    """
    Envía una imagen UML a Gemini (1.5-pro) y devuelve un JSON estructurado con:
    - Clases (nombre, atributos, métodos)
    - Relaciones clasificadas visualmente (composition, aggregation, generalization, association)
    """

    GEMINI_API_KEY = getattr(settings, "GEMINI_API_KEY", None)
    GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

    headers = {"Content-Type": "application/json"}
    params = {"key": GEMINI_API_KEY}

    # ===============================================================
    # 📘 Prompt mejorado: primero descripción visual, luego JSON UML
    # ===============================================================
    prompt_text = """
Primero observa cuidadosamente la imagen de un **diagrama de clases UML**.

Tu objetivo es identificar con precisión:
1️⃣ Las **clases** (rectángulos) y su contenido textual:
   - Nombre de la clase
   - Atributos (`nombre:tipo`)
   - Métodos (`nombre(parámetros):tipoRetorno`)

2️⃣ Las **relaciones** entre clases y sus símbolos visuales.
   Antes de generar el JSON, describe brevemente cómo se ve cada extremo del conector.
   Ejemplo de descripción interna que debes realizar (no la devuelvas):
   - "Rombo negro en extremo derecho" → tail.diamond="black"
   - "Rombo blanco en extremo izquierdo" → tail.diamond="white"
   - "Triángulo vacío grande apuntando hacia Entidad" → head.shape="triangle", head.fill="none", head.size="large"
   - "Triángulo pequeño negro apuntando a Gato" → head.shape="triangle", head.fill="solid", head.size="small"

📘 Reglas UML:
- Triángulo grande y vacío → `generalization`
- Triángulo pequeño y negro → `association`
- Rombo negro → `composition`
- Rombo blanco → `aggregation`
- Línea punteada → `dependency`

⚠️ Solo genera el JSON con esta estructura exacta (sin explicaciones):

{
  "nodes": [
    {
      "id": "uuid",
      "name": "NombreClase",
      "attributes": [
        {"name": "atributo", "type": "tipo"}
      ],
      "methods": [
        {"name": "metodo", "parameters": "", "returnType": ""}
      ]
    }
  ],
  "edges_raw": [
    {
      "id": "edge-uuid",
      "sourceName": "ClaseOrigen",
      "targetName": "ClaseDestino",
      "head": {
        "shape": "triangle|diamond|none",
        "fill": "solid|none|unknown",
        "size": "small|large|unknown"
      },
      "tail": {
        "diamond": "none|white|black"
      },
      "line": {
        "style": "solid|dashed|unknown"
      },
      "labels": ["1", "0..*"]
    }
  ]
}

NO escribas texto fuera del JSON.
"""

    # ===============================================================
    # 🚀 Enviar imagen a Gemini
    # ===============================================================
    data = {
        "contents": [
            {
                "parts": [
                    {"text": prompt_text},
                    {"inline_data": {"mime_type": mime_type, "data": image_base64}},
                ]
            }
        ]
    }

    try:
        response = requests.post(
            GEMINI_API_URL, headers=headers, params=params, json=data)
        response.raise_for_status()
        result = response.json()

        text_output = result["candidates"][0]["content"]["parts"][0]["text"]
        text_output = re.sub(r"^```json\s*|\s*```$", "",
                             text_output.strip(), flags=re.MULTILINE)
        parsed = json.loads(text_output)

        # Postprocesar relaciones según reglas determinísticas
        uml_json = _map_edges_to_relationships(parsed)
        return uml_json

    except Exception as e:
        return {"error": str(e)}

# ===============================================================
# 🔸 Clasificar conectores visuales → tipo UML
# ===============================================================


def _edge_to_relationship_type(edge):
    """
    Determina el tipo de relación UML a partir de los rasgos visuales detectados por Gemini.
    """
    head = edge.get("head", {})
    tail = edge.get("tail", {})
    line = edge.get("line", {})

    head_shape = head.get("shape")
    head_fill = head.get("fill")
    head_size = head.get("size")
    tail_diamond = tail.get("diamond")
    line_style = line.get("style")

    # 🔸 Reglas determinísticas
    if tail_diamond == "black":
        return "composition"
    if tail_diamond == "white":
        return "aggregation"
    if line_style == "dashed":
        return "dependency"

    if head_shape == "triangle":
        if head_size == "large" or head_fill == "none":
            return "generalization"  # triángulo grande/vacío → herencia
        if head_size == "small" or head_fill == "solid":
            return "association"  # triángulo pequeño/negro → asociación

    return "association"


def _map_edges_to_relationships(parsed_json):
    """
    Convierte los edges detectados por Gemini en relaciones UML bien orientadas.
    Corrige dirección si los símbolos están en el lado contrario.
    """
    nodes = parsed_json.get("nodes", [])
    edges = parsed_json.get("edges_raw", [])

    # Crear IDs por nombre
    name_to_id = {n.get("name"): (n.get("id") or str(uuid4())) for n in nodes}

    classes = [
        {
            "id": name_to_id[n.get("name")],
            "name": n.get("name"),
            "attributes": n.get("attributes", []),
            "methods": n.get("methods", []),
        }
        for n in nodes
    ]

    relationships = []

    for e in edges:
        rel_type = _edge_to_relationship_type(e)
        src = e.get("sourceName")
        tgt = e.get("targetName")
        labels = e.get("labels", [])

        # 🔹 Corrección automática de dirección
        # Si el rombo (black o white) está en el head, invertir
        head = e.get("head", {})
        tail = e.get("tail", {})

        if head.get("shape") == "diamond" or head.get("fill") in ["black", "white"]:
            src, tgt = tgt, src  # invertir dirección

        # Si el triángulo grande (herencia) está en el head, dejar igual
        # Si está en el tail (raro), invertir
        if tail.get("shape") == "triangle" and rel_type == "generalization":
            src, tgt = tgt, src

        if not src or not tgt:
            continue

        relationships.append(
            {
                "id": e.get("id") or str(uuid4()),
                "type": rel_type,
                "sourceId": name_to_id.get(src),
                "targetId": name_to_id.get(tgt),
                "labels": labels,
            }
        )

    return {"classes": classes, "relationships": relationships}
