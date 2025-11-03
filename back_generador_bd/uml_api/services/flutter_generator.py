import json
import os
from pathlib import Path
import unicodedata

class FlutterCRUDGenerator:
    def __init__(self, uml_json):
        self.uml_json = uml_json
        self.classes = uml_json.get('classes', [])
        self.relationships = uml_json.get('relationships', [])
        self.parsed_relationships = self._parse_relationships()

    def _parse_relationships(self):
      """Convierte relaciones UML en vínculos lógicos entre clases"""
      relations_map = {cls['id']: cls['name'] for cls in self.classes}
      parsed = []

      for rel in self.relationships:
          src = relations_map.get(rel.get('sourceId'))
          tgt = relations_map.get(rel.get('targetId'))
          if not src or not tgt:
              continue
          
          rtype = rel.get("type", "").lower()
          labels = rel.get("labels", [])

          if rtype == "generalization":
              parsed.append({"from": src, "to": tgt, "kind": "inherits"})
          elif rtype == "association":
              if "1..*" in labels or "0..*" in labels:
                  parsed.append({"from": src, "to": tgt, "kind": "one_to_many"})
              else:
                  parsed.append({"from": src, "to": tgt, "kind": "many_to_one"})
          elif rtype == "composition":
              parsed.append({"from": src, "to": tgt, "kind": "one_to_one"})
          elif rtype == "aggregation":
              parsed.append({"from": src, "to": tgt, "kind": "one_to_many"})
          elif rtype == "dependency":
              parsed.append({"from": src, "to": tgt, "kind": "many_to_one"})

      return parsed
        
    def generate_project(self, output_dir="generated_flutter_app"):
        """Genera el proyecto Flutter completo"""
        base_path = Path(output_dir)
        
        # Crear estructura de carpetas
        self._create_folder_structure(base_path)
        
        # Generar archivos base
        self._generate_pubspec(base_path)
        self._generate_main(base_path)
        self._generate_config(base_path)
        
        # Generar modelos, servicios y vistas para cada clase
        for clase in self.classes:
            self._generate_model(base_path, clase)
            self._generate_service(base_path, clase)
            self._generate_list_view(base_path, clase)
            self._generate_form_view(base_path, clase)
            self._generate_detail_view(base_path, clase)
        
        # Generar archivo de rutas
        self._generate_routes(base_path)
        
        print(f"✅ Proyecto Flutter generado en: {output_dir}")
        
    def _create_folder_structure(self, base_path):
        """Crea la estructura de carpetas del proyecto"""
        folders = [
            'lib/models',
            'lib/services',
            'lib/views',
            'lib/widgets',
        ]
        for folder in folders:
            (base_path / folder).mkdir(parents=True, exist_ok=True)
    
    def _generate_pubspec(self, base_path):
        """Genera el archivo pubspec.yaml"""
        content = """name: generated_crud_app
description: Aplicación Flutter generada automáticamente con CRUDs
publish_to: 'none'
version: 1.0.0+1

environment:
  sdk: '>=3.0.0 <4.0.0'

dependencies:
  flutter:
    sdk: flutter
  cupertino_icons: ^1.0.2
  http: ^1.1.0
  provider: ^6.0.5

dev_dependencies:
  flutter_test:
    sdk: flutter
  flutter_lints: ^2.0.0

flutter:
  uses-material-design: true
"""
        with open(base_path / 'pubspec.yaml', "w", encoding="utf-8") as f:
          f.write(self._sanitize(content))    
    def _generate_main(self, base_path):
        """Genera el archivo main.dart"""
        imports = '\n'.join([
            f"import 'views/{self._to_snake_case(c['name'])}_list_view.dart';"
            for c in self.classes
        ])
        
        content = f"""import 'package:flutter/material.dart';
{imports}

void main() {{
  runApp(const MyApp());
}}

class MyApp extends StatelessWidget {{
  const MyApp({{super.key}});

  @override
  Widget build(BuildContext context) {{
    return MaterialApp(
      title: 'CRUD Generator',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.deepPurple),
        useMaterial3: true,
      ),
      home: const HomePage(),
    );
  }}
}}

class HomePage extends StatelessWidget {{
  const HomePage({{super.key}});

  @override
  Widget build(BuildContext context) {{
    return Scaffold(
      appBar: AppBar(
        title: const Text('Gestión de Clases'),
        backgroundColor: Theme.of(context).colorScheme.inversePrimary,
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
{self._generate_home_cards()}
        ],
      ),
    );
  }}
}}
"""
        (base_path / 'lib' / 'main.dart').write_text(self._sanitize(content), encoding="utf-8", newline="\n")
    
    def _generate_home_cards(self):
        """Genera las tarjetas de navegación en el home"""
        cards = []
        for clase in self.classes:
            name = clase['name']
            snake_name = self._to_snake_case(name)
            cards.append(f"""          Card(
            margin: const EdgeInsets.only(bottom: 16),
            child: ListTile(
              leading: const Icon(Icons.table_chart, size: 40),
              title: Text('{name}'),
              subtitle: Text('Gestionar {name}'),
              trailing: const Icon(Icons.arrow_forward_ios),
              onTap: () {{
                Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (context) => {name}ListView(),
                  ),
                );
              }},
            ),
          )""")
        return ',\n'.join(cards)
    
    def _generate_config(self, base_path):
        """Genera el archivo de configuración para el API"""
        content = """class ApiConfig {
  // Cambia esta URL según tu backend
  static const String baseUrl = 'http://localhost:9000/api';
  
  // Para Android Emulator, usa: 'http://10.0.2.2:9000/api'
  // Para iOS Simulator, usa: 'http://localhost:9000/api'
  // Para dispositivo físico, usa la IP de tu computadora: 'http://192.168.x.x:9000/api'
}
"""
        (base_path / 'lib' / 'config.dart').write_text(content, encoding="utf-8", newline="\n")
    
    def _generate_model(self, base_path, clase):
      """Genera el modelo de datos, con imports y parsing de relaciones"""
      name = clase['name']
      relationships = self.parsed_relationships
      attributes = clase.get('attributes', [])

      # Detectar clase padre (herencia)
      parent_class = None
      for rel in relationships:
          if rel["from"] == name and rel["kind"] == "inherits":
              parent_class = rel["to"]
              break

      # IMPORTANTE: El primer atributo es la PK
      # Detectar tipo de PK (numérica o string)
      pk_attr = attributes[0] if attributes and not parent_class else None
      pk_type = None
      pk_name = None
      is_numeric_pk = False
      
      if pk_attr:
          pk_name = pk_attr['name']
          pk_type = self._convert_type(pk_attr['type'])
          is_numeric_pk = pk_type in ['int', 'double']

      # Detectar modelos relacionados para importar
      related_models = set()
      if parent_class:
          related_models.add(parent_class)
      for rel in relationships:
          if rel["from"] == name and rel["kind"] in ["one_to_one", "one_to_many"]:
              related_models.add(rel["to"])

      imports = "\n".join([
          f"import '{self._to_snake_case(model)}.dart';"
          for model in sorted(related_models)
      ])

      # Clase extends o normal
      class_declaration = f"class {name} extends {parent_class}" if parent_class else f"class {name}"

      # Propiedades (solo las propias, NO las heredadas)
      properties = []
      
      # Si NO tiene padre, agregar todos los atributos normalmente
      # Si SÍ tiene padre, NO agregar el primer atributo (PK heredada)
      start_index = 0
      if not parent_class:
          # Sin herencia: agregar todos los atributos incluyendo PK
          for attr in attributes:
              dart_type = self._convert_type(attr['type'])
              properties.append(f"  final {dart_type} {attr['name']};")
      else:
          # Con herencia: NO agregar atributos propios, todos vienen del padre o son propios sin PK
          # Solo agregar atributos que NO son PK (la PK viene del padre)
          for attr in attributes:
              dart_type = self._convert_type(attr['type'])
              properties.append(f"  final {dart_type} {attr['name']};")

      # Relaciones - Solo agregar si no existe ya un atributo con ese nombre
      # Normalizar nombres eliminando guiones bajos y convirtiendo a lowercase para comparación
      existing_attr_names = {attr['name'].lower().replace('_', '') for attr in attributes}
      rel_fields = []
      for rel in relationships:
          if rel["from"] == name:
              if rel["kind"] == "many_to_one":
                  field_name = f"{self._to_snake_case(rel['to'])}Id"
                  normalized_field = field_name.lower().replace('_', '')
                  if normalized_field not in existing_attr_names:
                      rel_fields.append(f"  final String {field_name};")
              elif rel["kind"] == "one_to_many":
                  # Mantener en singular como viene del backend
                  field_name = self._to_snake_case(rel['to'])
                  normalized_field = field_name.lower().replace('_', '')
                  if normalized_field not in existing_attr_names:
                      rel_fields.append(f"  final List<{rel['to']}> {field_name};")
              elif rel["kind"] == "one_to_one":
                  field_name = self._to_snake_case(rel['to'])
                  normalized_field = field_name.lower().replace('_', '')
                  if normalized_field not in existing_attr_names:
                      # Hacer nullable porque el backend puede no enviarlo
                      rel_fields.append(f"  final {rel['to']}? {field_name};")
      properties.extend(rel_fields)

      # Constructor con super() si hay herencia
      constructor_params_list = []
      super_params_list = []
      
      # Si tiene padre, necesitamos pasar sus parámetros al super()
      if parent_class:
          # Función recursiva para obtener TODOS los atributos del padre (incluyendo PK)
          def get_all_parent_attributes(class_name):
              attrs = []
              current_class = next((c for c in self.classes if c['name'] == class_name), None)
              if current_class:
                  # Buscar si esta clase también tiene padre
                  parent_rels = [r for r in relationships if r["from"] == class_name and r["kind"] == "inherits"]
                  if parent_rels:
                      parent_name = parent_rels[0]["to"]
                      attrs.extend(get_all_parent_attributes(parent_name))
                  # Agregar atributos propios del padre
                  attrs.extend(current_class.get('attributes', []))
              return attrs
          
          # Obtener TODOS los atributos del padre (recursivamente)
          parent_attrs = get_all_parent_attributes(parent_class)
          
          # Agregar parámetros del padre para el super()
          for attr in parent_attrs:
              attr_name = attr['name']
              attr_type = self._convert_type(attr['type'])
              super_params_list.append(f"{attr_name}: {attr_name}")
              constructor_params_list.append(f"required {attr_type} {attr_name}")
      else:
          # Si no tiene padre, los atributos se agregan abajo con this.
          pass
      
      # Agregar parámetros propios (con this. si no hay padre, sin this. si hay padre)
      for attr in attributes:
          constructor_params_list.append(f"required this.{attr['name']}")
      
      # Normalizar para comparación
      existing_attr_names_normalized = {attr['name'].lower().replace('_', '') for attr in attributes}
      
      for rel in relationships:
          if rel["from"] == name:
              if rel["kind"] == "one_to_many":
                  # Mantener en singular
                  field_name = self._to_snake_case(rel['to'])
                  normalized_field = field_name.lower().replace('_', '')
                  if normalized_field not in existing_attr_names_normalized:
                      constructor_params_list.append(f"required this.{field_name}")
              elif rel["kind"] == "one_to_one":
                  field_name = self._to_snake_case(rel['to'])
                  normalized_field = field_name.lower().replace('_', '')
                  if normalized_field not in existing_attr_names_normalized:
                      # Hacer opcional porque puede ser null
                      constructor_params_list.append(f"this.{field_name}")
      constructor_params = ", ".join(constructor_params_list)
      
      # Generar llamada al super() si hay herencia
      super_call = ""
      if parent_class and super_params_list:
          super_call = f" : super({', '.join(super_params_list)})"

      # fromJson
      from_json_fields = []
      
      # Si tiene padre, incluir TODOS los atributos heredados (incluyendo PK)
      if parent_class:
          # Función recursiva para obtener todos los atributos del padre
          def get_all_parent_attributes_for_json(class_name):
              attrs = []
              current_class = next((c for c in self.classes if c['name'] == class_name), None)
              if current_class:
                  # Buscar si esta clase también tiene padre
                  parent_rels = [r for r in relationships if r["from"] == class_name and r["kind"] == "inherits"]
                  if parent_rels:
                      parent_name = parent_rels[0]["to"]
                      attrs.extend(get_all_parent_attributes_for_json(parent_name))
                  # Agregar atributos propios del padre
                  attrs.extend(current_class.get('attributes', []))
              return attrs
          
          parent_attrs = get_all_parent_attributes_for_json(parent_class)
          
          # Agregar todos los atributos heredados al fromJson
          for attr in parent_attrs:
              attr_type = self._convert_type(attr['type'])
              json_key = self._to_backend_json_key(attr['name'])
              if attr_type == 'int':
                  from_json_fields.append(f"{attr['name']}: json['{json_key}'] is int ? json['{json_key}'] : int.tryParse(json['{json_key}']?.toString() ?? '0') ?? 0")
              elif attr_type == 'double':
                  from_json_fields.append(f"{attr['name']}: json['{json_key}'] is double ? json['{json_key}'] : double.tryParse(json['{json_key}']?.toString() ?? '0.0') ?? 0.0")
              else:
                  from_json_fields.append(f"{attr['name']}: json['{json_key}']")
      
      # Agregar campos propios
      for attr in attributes:
          attr_type = self._convert_type(attr['type'])
          json_key = self._to_backend_json_key(attr['name'])
          if attr_type == 'int':
              from_json_fields.append(f"{attr['name']}: json['{json_key}'] is int ? json['{json_key}'] : int.tryParse(json['{json_key}']?.toString() ?? '0') ?? 0")
          elif attr_type == 'double':
              from_json_fields.append(f"{attr['name']}: json['{json_key}'] is double ? json['{json_key}'] : double.tryParse(json['{json_key}']?.toString() ?? '0.0') ?? 0.0")
          else:
              from_json_fields.append(f"{attr['name']}: json['{json_key}']")

      # Agregar relaciones
      for rel in relationships:
          if rel["from"] == name:
              rel_name = self._to_snake_case(rel['to'])
              json_key = self._to_backend_json_key(rel_name)
              if rel["kind"] == "one_to_one":
                  from_json_fields.append(f"{rel_name}: json['{json_key}'] != null ? {rel['to']}.fromJson(json['{json_key}']) : null")
              elif rel["kind"] == "one_to_many":
                  # Mantener en singular como viene del backend
                  # Manejar tres casos: Lista, Objeto único, o null
                  from_json_fields.append(
                      f"{rel_name}: (json['{json_key}'] is List) ? (json['{json_key}'] as List<dynamic>).map((e) => {rel['to']}.fromJson(e)).toList() : (json['{json_key}'] is Map) ? [{rel['to']}.fromJson(json['{json_key}'])] : []"
                  )

      # toJson - incluir campos heredados también
      to_json_fields = []
      
      # Si tiene padre, incluir todos los campos heredados (incluyendo PK)
      if parent_class:
          # Función recursiva para obtener todos los atributos del padre
          def get_all_parent_attributes_for_tojson(class_name):
              attrs = []
              current_class = next((c for c in self.classes if c['name'] == class_name), None)
              if current_class:
                  # Buscar si esta clase también tiene padre
                  parent_rels = [r for r in relationships if r["from"] == class_name and r["kind"] == "inherits"]
                  if parent_rels:
                      parent_name = parent_rels[0]["to"]
                      attrs.extend(get_all_parent_attributes_for_tojson(parent_name))
                  # Agregar atributos propios del padre
                  attrs.extend(current_class.get('attributes', []))
              return attrs
          
          parent_attrs = get_all_parent_attributes_for_tojson(parent_class)
          
          # Agregar todos los atributos heredados al toJson
          for attr in parent_attrs:
              json_key = self._to_backend_json_key(attr['name'])
              to_json_fields.append(f"'{json_key}': {attr['name']}")
      
      # Agregar campos propios
      for attr in attributes:
          json_key = self._to_backend_json_key(attr['name'])
          to_json_fields.append(f"'{json_key}': {attr['name']}")
      
      # Agregar relaciones
      for rel in relationships:
          if rel["from"] == name:
              rel_name = self._to_snake_case(rel['to'])
              json_key = self._to_backend_json_key(rel_name)
              if rel["kind"] == "one_to_one":
                  # Manejar el caso cuando es null
                  to_json_fields.append(f"'{json_key}': {rel_name}?.toJson()")
              elif rel["kind"] == "one_to_many":
                  # El backend puede esperar un objeto único en lugar de lista
                  # Si la lista tiene elementos, enviar el primero como objeto
                  # Si está vacía, enviar null
                  to_json_fields.append(
                      f"'{json_key}': {rel_name}.isNotEmpty ? {rel_name}.first.toJson() : null"
                  )

      # Generar el constructor - no se necesitan parámetros extra para PK
      # La PK se maneja como el primer atributo
      id_param = ""
      
      # fromJson - no se necesita manejo especial, la PK viene en los atributos
      id_from_json = ""

      # toJson - no se necesita manejo especial, la PK está en los atributos  
      id_to_json = ""

      content = f"""{imports}

  {class_declaration} {{
  {chr(10).join(properties)}

    {name}({{
      {id_param}
      {constructor_params},
    }}){super_call};

    factory {name}.fromJson(Map<String, dynamic> json) {{
      return {name}(
        {id_from_json}
        {', '.join(from_json_fields)},
      );
    }}

    Map<String, dynamic> toJson() {{
      return {{
        {id_to_json}
        {', '.join(to_json_fields)},
      }};
    }}
  }}
  """
      file_path = base_path / 'lib' / 'models' / f'{self._to_snake_case(name)}.dart'
      file_path.write_text(self._sanitize(content), encoding="utf-8", newline="\n")


    
    def _generate_service(self, base_path, clase):
        """Genera el servicio para operaciones CRUD, con relaciones anidadas"""
        name = clase['name']
        snake_name = self._to_snake_case(name)
        # Convertir nombre de clase al formato del backend para URLs
        backend_url_name = self._to_backend_json_key(name)
        relationships = [r for r in self.parsed_relationships if r["from"] == name]
        attributes = clase.get('attributes', [])

        # Detectar herencia y obtener todos los atributos (propios + heredados)
        parent_class = None
        for rel in relationships:
            if rel["kind"] == "inherits":
                parent_class = rel["to"]
                break
        
        # Función recursiva para obtener todos los atributos heredados
        def get_all_attributes(class_name):
            attrs = []
            current_class = next((c for c in self.classes if c['name'] == class_name), None)
            if current_class:
                # Primero obtener atributos del padre (si existe)
                parent_rels = [r for r in self.parsed_relationships if r["from"] == class_name and r["kind"] == "inherits"]
                if parent_rels:
                    parent_name = parent_rels[0]["to"]
                    attrs.extend(get_all_attributes(parent_name))
                # Luego agregar atributos propios
                attrs.extend(current_class.get('attributes', []))
            return attrs
        
        all_attributes = get_all_attributes(name)

        # Verificar si la clase tiene un atributo 'id' definido
        has_id = any(attr['name'].lower() == 'id' for attr in all_attributes)

        # Importar modelos relacionados
        related_models = [
            rel["to"] for rel in relationships if rel["kind"] in ["one_to_one", "one_to_many"]
        ]
        imports = "\n".join([
            f"import '../models/{self._to_snake_case(model)}.dart';"
            for model in related_models
        ])

        content = f"""{imports}
import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/{snake_name}.dart';
import '../config.dart';

class {name}Service {{
  static const String baseUrl = ApiConfig.baseUrl;
  
  Future<List<{name}>> getAll() async {{
    try {{
      final response = await http.get(
        Uri.parse('$baseUrl/{backend_url_name}'),
        headers: {{'Content-Type': 'application/json'}},
      );

      if (response.statusCode == 200) {{
        final List<dynamic> jsonList = json.decode(response.body);
        return jsonList.map((json) => {name}.fromJson(json)).toList();
      }} else {{
        throw Exception('Error al cargar {name}s: ${{response.statusCode}}');
      }}
    }} catch (e) {{
      throw Exception('Error de conexión: $e');
    }}
  }}

  Future<{name}?> getById(String id) async {{
    try {{
      final response = await http.get(
        Uri.parse('$baseUrl/{backend_url_name}/$id'),
        headers: {{'Content-Type': 'application/json'}},
      );

      if (response.statusCode == 200) {{
        return {name}.fromJson(json.decode(response.body));
      }} else if (response.statusCode == 404) {{
        return null;
      }} else {{
        throw Exception('Error al obtener {name}: ${{response.statusCode}}');
      }}
    }} catch (e) {{
      throw Exception('Error de conexión: $e');
    }}
  }}

  Future<{name}> create({name} item) async {{
    try {{
      final response = await http.post(
        Uri.parse('$baseUrl/{backend_url_name}'),
        headers: {{'Content-Type': 'application/json'}},
        body: json.encode(item.toJson()),
      );

      if (response.statusCode == 201 || response.statusCode == 200) {{
        return {name}.fromJson(json.decode(response.body));
      }} else {{
        throw Exception('Error al crear {name}: ${{response.statusCode}} - ${{response.body}}');
      }}
    }} catch (e) {{
      throw Exception('Error de conexión: $e');
    }}
  }}

  Future<{name}> update(String id, {name} item) async {{
    try {{
      final response = await http.put(
        Uri.parse('$baseUrl/{backend_url_name}/$id'),
        headers: {{'Content-Type': 'application/json'}},
        body: json.encode(item.toJson()),
      );

      if (response.statusCode == 200) {{
        return {name}.fromJson(json.decode(response.body));
      }} else {{
        throw Exception('Error al actualizar {name}: ${{response.statusCode}} - ${{response.body}}');
      }}
    }} catch (e) {{
      throw Exception('Error de conexión: $e');
    }}
  }}

  Future<void> delete(String id) async {{
    try {{
      final response = await http.delete(
        Uri.parse('$baseUrl/{backend_url_name}/$id'),
        headers: {{'Content-Type': 'application/json'}},
      );

      if (response.statusCode != 204 && response.statusCode != 200) {{
        throw Exception('Error al eliminar {name}: ${{response.statusCode}}');
      }}
    }} catch (e) {{
      throw Exception('Error de conexión: $e');
    }}
  }}
}}
"""
        file_path = base_path / 'lib' / 'services' / f'{snake_name}_service.dart'
        file_path.write_text(self._sanitize(content), encoding="utf-8", newline="\n")

    
    def _generate_list_view(self, base_path, clase):
        """Genera la vista de listado"""
        name = clase['name']
        snake_name = self._to_snake_case(name)
        relationships = [r for r in self.parsed_relationships if r["from"] == name]
        attributes = clase.get('attributes', [])
        
        # Detectar herencia para obtener todos los atributos
        parent_class = None
        for rel in relationships:
            if rel["kind"] == "inherits":
                parent_class = rel["to"]
                break
        
        # Función recursiva para obtener todos los atributos heredados
        def get_all_attributes(class_name):
            attrs = []
            current_class = next((c for c in self.classes if c['name'] == class_name), None)
            if current_class:
                parent_rels = [r for r in self.parsed_relationships if r["from"] == class_name and r["kind"] == "inherits"]
                if parent_rels:
                    parent_name = parent_rels[0]["to"]
                    attrs.extend(get_all_attributes(parent_name))
                attrs.extend(current_class.get('attributes', []))
            return attrs
        
        all_attributes = get_all_attributes(name)
        
        # El primer atributo es la PK
        pk_attr = all_attributes[0] if all_attributes else None
        pk_name = pk_attr['name'] if pk_attr else 'id'
        
        # Segundo atributo para mostrar en la lista (o el primero si solo hay uno)
        display_attr = all_attributes[1]['name'] if len(all_attributes) > 1 else pk_name
        
        content = f"""import 'package:flutter/material.dart';
import '../models/{snake_name}.dart';
import '../services/{snake_name}_service.dart';
import '{snake_name}_form_view.dart';
import '{snake_name}_detail_view.dart';

class {name}ListView extends StatefulWidget {{
  const {name}ListView({{super.key}});

  @override
  State<{name}ListView> createState() => _{name}ListViewState();
}}

class _{name}ListViewState extends State<{name}ListView> {{
  final {name}Service _service = {name}Service();
  List<{name}> _items = [];
  bool _isLoading = true;

  @override
  void initState() {{
    super.initState();
    _loadItems();
  }}

  Future<void> _loadItems() async {{
    setState(() => _isLoading = true);
    try {{
      final items = await _service.getAll();
      setState(() {{
        _items = items;
        _isLoading = false;
      }});
    }} catch (e) {{
      setState(() => _isLoading = false);
      if (mounted) {{
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error al cargar: $e')),
        );
      }}
    }}
  }}

  Future<void> _deleteItem(String id) async {{
    try {{
      await _service.delete(id);
      _loadItems();
      if (mounted) {{
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Eliminado exitosamente')),
        );
      }}
    }} catch (e) {{
      if (mounted) {{
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error al eliminar: $e')),
        );
      }}
    }}
  }}

  @override
  Widget build(BuildContext context) {{
    return Scaffold(
      appBar: AppBar(
        title: const Text('{name}'),
        backgroundColor: Theme.of(context).colorScheme.inversePrimary,
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _items.isEmpty
              ? const Center(
                  child: Text('No hay registros. ¡Crea uno nuevo!'),
                )
              : ListView.builder(
                  itemCount: _items.length,
                  itemBuilder: (context, index) {{
                    final item = _items[index];
                    return Card(
                      margin: const EdgeInsets.symmetric(
                        horizontal: 16,
                        vertical: 8,
                      ),
                      child: ListTile(
                        title: Text(item.{display_attr}.toString()),
                        subtitle: Text('{pk_name}: ${{item.{pk_name}}}'),
                        trailing: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            IconButton(
                              icon: const Icon(Icons.edit),
                              onPressed: () async {{
                                await Navigator.push(
                                  context,
                                  MaterialPageRoute(
                                    builder: (context) => {name}FormView(
                                      item: item,
                                    ),
                                  ),
                                );
                                _loadItems();
                              }},
                            ),
                            IconButton(
                              icon: const Icon(Icons.delete),
                              color: Colors.red,
                              onPressed: () {{
                                showDialog(
                                  context: context,
                                  builder: (context) => AlertDialog(
                                    title: const Text('Confirmar'),
                                    content: const Text(
                                      '¿Deseas eliminar este registro?',
                                    ),
                                    actions: [
                                      TextButton(
                                        onPressed: () => Navigator.pop(context),
                                        child: const Text('Cancelar'),
                                      ),
                                      TextButton(
                                        onPressed: () {{
                                          Navigator.pop(context);
                                          _deleteItem(item.{pk_name}.toString());
                                        }},
                                        child: const Text('Eliminar'),
                                      ),
                                    ],
                                  ),
                                );
                              }},
                            ),
                          ],
                        ),
                        onTap: () {{
                          Navigator.push(
                            context,
                            MaterialPageRoute(
                              builder: (context) => {name}DetailView(item: item),
                            ),
                          );
                        }},
                      ),
                    );
                  }},
                ),
      floatingActionButton: FloatingActionButton(
        onPressed: () async {{
          await Navigator.push(
            context,
            MaterialPageRoute(
              builder: (context) => const {name}FormView(),
            ),
          );
          _loadItems();
        }},
        child: const Icon(Icons.add),
      ),
    );
  }}
}}
"""
        file_path = base_path / 'lib' / 'views' / f'{snake_name}_list_view.dart'
        file_path.write_text(content, encoding="utf-8", newline="\n")
    
    def _generate_form_view(self, base_path, clase):
        """Genera la vista de formulario (crear/editar)"""
        name = clase['name']
        snake_name = self._to_snake_case(name)
        relationships = [r for r in self.parsed_relationships if r["from"] == name]
        attributes = clase.get('attributes', [])
        
        # Detectar herencia y obtener todos los atributos (propios + heredados)
        all_attributes = []
        parent_class = None
        for rel in relationships:
            if rel["kind"] == "inherits":
                parent_class = rel["to"]
                break
        
        # Función recursiva para obtener todos los atributos heredados
        def get_all_attributes(class_name):
            attrs = []
            current_class = next((c for c in self.classes if c['name'] == class_name), None)
            if current_class:
                # Primero obtener atributos del padre (si existe)
                parent_rels = [r for r in self.parsed_relationships if r["from"] == class_name and r["kind"] == "inherits"]
                if parent_rels:
                    parent_name = parent_rels[0]["to"]
                    attrs.extend(get_all_attributes(parent_name))
                # Luego agregar atributos propios
                attrs.extend(current_class.get('attributes', []))
            return attrs
        
        all_attributes = get_all_attributes(name)
        
        # Detectar tipo de PK (primer atributo si no hay herencia)
        pk_attr = all_attributes[0] if all_attributes else None
        pk_type = self._convert_type(pk_attr['type']) if pk_attr else 'String'
        is_numeric_pk = pk_type in ['int', 'double'] if pk_attr else False
        pk_name = pk_attr['name'] if pk_attr else 'id'
        
        # Verificar si la clase tiene un atributo 'id' definido
        has_id = any(attr['name'].lower() == 'id' for attr in all_attributes)
        
        # Normalizar para comparación (declarar temprano para uso posterior)
        existing_attr_names_normalized = {attr['name'].lower().replace('_', '') for attr in all_attributes}
        
        # Generar controladores
        # - Para PK numérica (autoincremental): NO generar controlador (solo en edición, readonly)
        # - Para PK string: SÍ generar controlador (se debe ingresar manualmente)
        controllers_list = []
        for i, attr in enumerate(all_attributes):
            # Si es la PK (primer atributo) y es numérica, no generar controlador para creación
            if i == 0 and is_numeric_pk and parent_class is None:
                # Solo se mostrará readonly en edición
                continue
            # Para otras PKs string o atributos normales, generar controlador
            controllers_list.append(f"final TextEditingController _{attr['name']}Controller = TextEditingController();")
        
        # Agregar variables para relaciones many_to_one
        for rel in relationships:
            if rel["kind"] == "many_to_one":
                controllers_list.append(f"String? _selected{rel['to']}Id;")
        
        # Agregar variables para relaciones one_to_one
        for rel in relationships:
            if rel["kind"] == "one_to_one":
                field_name = self._to_snake_case(rel['to'])
                normalized_field = field_name.lower().replace('_', '')
                if normalized_field not in existing_attr_names_normalized:
                    controllers_list.append(f"String? _selected{rel['to']}Id;")
        
        # Agregar variables para relaciones one_to_many
        for rel in relationships:
            if rel["kind"] == "one_to_many":
                # Mantener en singular
                field_name = self._to_snake_case(rel['to'])
                normalized_field = field_name.lower().replace('_', '')
                if normalized_field not in existing_attr_names_normalized:
                    controllers_list.append(f"List<String> _selected{rel['to']}Ids = [];")
        
        controllers = '\n  '.join(controllers_list)
        
        # Inicializar controladores si es edición - incluir campos heredados
        init_controllers_list = []
        for i, attr in enumerate(all_attributes):
            # Si es PK numérica, no hay controlador para inicializar (solo lectura)
            if i == 0 and is_numeric_pk and parent_class is None:
                continue
            # Inicializar otros controladores
            init_controllers_list.append(f"_{attr['name']}Controller.text = widget.item!.{attr['name']}.toString();")
        
        # Inicializar relaciones many_to_one
        existing_attr_names_normalized = {attr['name'].lower().replace('_', '') for attr in attributes}
        for rel in relationships:
            if rel["kind"] == "many_to_one":
                field_name = f"{self._to_snake_case(rel['to'])}Id"
                normalized_field = field_name.lower().replace('_', '')
                if normalized_field not in existing_attr_names_normalized:
                    init_controllers_list.append(f"_selected{rel['to']}Id = widget.item!.{field_name};")
        
        # Inicializar relaciones one_to_one
        for rel in relationships:
            if rel["kind"] == "one_to_one":
                field_name = self._to_snake_case(rel['to'])
                normalized_field = field_name.lower().replace('_', '')
                if normalized_field not in existing_attr_names_normalized:
                    # Obtener el nombre de la PK de la clase relacionada
                    related_class = next((c for c in self.classes if c['name'] == rel['to']), None)
                    if related_class:
                        # Función recursiva para obtener PK de la clase relacionada
                        def get_pk_name(class_name):
                            current = next((c for c in self.classes if c['name'] == class_name), None)
                            if current:
                                # Buscar herencia
                                parent_rels = [r for r in self.parsed_relationships if r["from"] == class_name and r["kind"] == "inherits"]
                                if parent_rels:
                                    # Si tiene padre, la PK está en el padre
                                    return get_pk_name(parent_rels[0]["to"])
                                # Si no tiene padre, el primer atributo es la PK
                                attrs = current.get('attributes', [])
                                if attrs:
                                    return attrs[0]['name']
                            return 'id'
                        related_pk = get_pk_name(rel['to'])
                        # Usar acceso condicional seguro porque el campo one_to_one puede ser null
                        init_controllers_list.append(f"_selected{rel['to']}Id = widget.item!.{field_name}?.{related_pk}.toString();")
        
        # Inicializar relaciones one_to_many
        for rel in relationships:
            if rel["kind"] == "one_to_many":
                # Mantener en singular
                field_name = self._to_snake_case(rel['to'])
                normalized_field = field_name.lower().replace('_', '')
                if normalized_field not in existing_attr_names_normalized:
                    # Obtener el nombre de la PK de la clase relacionada
                    related_class = next((c for c in self.classes if c['name'] == rel['to']), None)
                    if related_class:
                        # Función recursiva para obtener PK de la clase relacionada
                        def get_pk_name_many(class_name):
                            current = next((c for c in self.classes if c['name'] == class_name), None)
                            if current:
                                # Buscar herencia
                                parent_rels = [r for r in self.parsed_relationships if r["from"] == class_name and r["kind"] == "inherits"]
                                if parent_rels:
                                    return get_pk_name_many(parent_rels[0]["to"])
                                attrs = current.get('attributes', [])
                                if attrs:
                                    return attrs[0]['name']
                            return 'id'
                        related_pk = get_pk_name_many(rel['to'])
                        init_controllers_list.append(f"_selected{rel['to']}Ids = widget.item!.{field_name}.map((e) => e.{related_pk}.toString()).toList();")
        
        init_controllers = '\n      '.join(init_controllers_list)
        
        # Generar campos del formulario
        form_fields = []
        for i, attr in enumerate(all_attributes):
            dart_type = self._convert_type(attr['type'])
            keyboard_type = 'TextInputType.number' if dart_type in ['int', 'double'] else 'TextInputType.text'
            
            # Si es PK numérica y estamos EDITANDO, mostrar campo readonly
            if i == 0 and is_numeric_pk and parent_class is None:
                form_fields.append(f"""            if (widget.item != null)
              TextFormField(
                initialValue: widget.item!.{attr['name']}.toString(),
                decoration: const InputDecoration(
                  labelText: '{attr['name']} (Auto)',
                  border: OutlineInputBorder(),
                ),
                enabled: false,
              )""")
                continue
            
            # Para PK string o atributos normales, campo editable
            form_fields.append(f"""            TextFormField(
              controller: _{attr['name']}Controller,
              decoration: const InputDecoration(
                labelText: '{attr['name']}',
                border: OutlineInputBorder(),
              ),
              keyboardType: {keyboard_type},
              validator: (value) {{
                if (value == null || value.isEmpty) {{
                  return 'Este campo es requerido';
                }}
                return null;
              }},
            )""")
        
        # Relaciones ManyToOne → Dropdown (sin coma al final)
        for rel in relationships:
            if rel["kind"] == "many_to_one":
                # Obtener la PK y display attr de la clase relacionada
                related_class = next((c for c in self.classes if c['name'] == rel['to']), None)
                
                # Función para obtener la PK de una clase (considerando herencia)
                def get_related_pk(class_name):
                    current = next((c for c in self.classes if c['name'] == class_name), None)
                    if current:
                        parent_rels = [r for r in self.parsed_relationships if r["from"] == class_name and r["kind"] == "inherits"]
                        if parent_rels:
                            return get_related_pk(parent_rels[0]["to"])
                        attrs = current.get('attributes', [])
                        if attrs:
                            return attrs[0]['name']
                    return 'id'
                
                related_pk = get_related_pk(rel['to'])
                display_attr = related_pk
                
                if related_class:
                    attrs = related_class.get('attributes', [])
                    # Buscar el primer atributo que no sea la PK para mostrar
                    for attr in attrs:
                        if attr['name'] != related_pk:
                            display_attr = attr['name']
                            break
                
                form_fields.append(f"""FutureBuilder<List<{rel['to']}>>(
              future: {rel['to']}Service().getAll(),
              builder: (context, snapshot) {{
                if (!snapshot.hasData) return const CircularProgressIndicator();
                return DropdownButtonFormField<String>(
                  decoration: const InputDecoration(labelText: '{rel['to']}'),
                  value: _selected{rel['to']}Id,
                  items: snapshot.data!.map((e) => DropdownMenuItem(
                    value: e.{related_pk}.toString(),
                    child: Text(e.{display_attr}.toString()),
                  )).toList(),
                  onChanged: (v) {{
                    setState(() {{
                      _selected{rel['to']}Id = v;
                    }});
                  }},
                  validator: (value) {{
                    if (value == null || value.isEmpty) {{
                      return 'Este campo es requerido';
                    }}
                    return null;
                  }},
                );
              }},
            )""")
        
        # Relaciones OneToOne → Dropdown
        for rel in relationships:
            if rel["kind"] == "one_to_one":
                field_name = self._to_snake_case(rel['to'])
                normalized_field = field_name.lower().replace('_', '')
                if normalized_field not in existing_attr_names_normalized:
                    # Obtener la PK y display attr de la clase relacionada
                    related_class = next((c for c in self.classes if c['name'] == rel['to']), None)
                    
                    # Función para obtener la PK de una clase (considerando herencia)
                    def get_related_pk_one(class_name):
                        current = next((c for c in self.classes if c['name'] == class_name), None)
                        if current:
                            parent_rels = [r for r in self.parsed_relationships if r["from"] == class_name and r["kind"] == "inherits"]
                            if parent_rels:
                                return get_related_pk_one(parent_rels[0]["to"])
                            attrs = current.get('attributes', [])
                            if attrs:
                                return attrs[0]['name']
                        return 'id'
                    
                    related_pk = get_related_pk_one(rel['to'])
                    display_attr = related_pk
                    
                    if related_class:
                        attrs = related_class.get('attributes', [])
                        # Buscar el primer atributo que no sea la PK para mostrar
                        for attr in attrs:
                            if attr['name'] != related_pk:
                                display_attr = attr['name']
                                break
                    
                    form_fields.append(f"""FutureBuilder<List<{rel['to']}>>(
              future: {rel['to']}Service().getAll(),
              builder: (context, snapshot) {{
                if (!snapshot.hasData) return const CircularProgressIndicator();
                return DropdownButtonFormField<String>(
                  decoration: const InputDecoration(labelText: '{rel['to']}'),
                  value: _selected{rel['to']}Id,
                  items: snapshot.data!.map((e) => DropdownMenuItem(
                    value: e.{related_pk}.toString(),
                    child: Text(e.{display_attr}.toString()),
                  )).toList(),
                  onChanged: (v) {{
                    setState(() {{
                      _selected{rel['to']}Id = v;
                    }});
                  }},
                  validator: (value) {{
                    if (value == null || value.isEmpty) {{
                      return 'Este campo es requerido';
                    }}
                    return null;
                  }},
                );
              }},
            )""")
        
        # Relaciones OneToMany → Dropdown simple (aunque sea lista, el backend espera solo un objeto)
        for rel in relationships:
            if rel["kind"] == "one_to_many":
                # Mantener en singular
                field_name = self._to_snake_case(rel['to'])
                normalized_field = field_name.lower().replace('_', '')
                if normalized_field not in existing_attr_names_normalized:
                    # Obtener la PK y display attr de la clase relacionada
                    related_class = next((c for c in self.classes if c['name'] == rel['to']), None)
                    
                    # Función para obtener la PK de una clase (considerando herencia)
                    def get_related_pk_many(class_name):
                        current = next((c for c in self.classes if c['name'] == class_name), None)
                        if current:
                            parent_rels = [r for r in self.parsed_relationships if r["from"] == class_name and r["kind"] == "inherits"]
                            if parent_rels:
                                return get_related_pk_many(parent_rels[0]["to"])
                            attrs = current.get('attributes', [])
                            if attrs:
                                return attrs[0]['name']
                        return 'id'
                    
                    related_pk = get_related_pk_many(rel['to'])
                    display_attr = related_pk
                    
                    if related_class:
                        attrs = related_class.get('attributes', [])
                        # Buscar el primer atributo que no sea la PK para mostrar
                        for attr in attrs:
                            if attr['name'] != related_pk:
                                display_attr = attr['name']
                                break
                    
                    # Generar dropdown simple en lugar de selector múltiple
                    form_fields.append(f"""FutureBuilder<List<{rel['to']}>>(
              future: {rel['to']}Service().getAll(),
              builder: (context, snapshot) {{
                if (!snapshot.hasData) return const CircularProgressIndicator();
                return DropdownButtonFormField<String>(
                  decoration: const InputDecoration(labelText: '{rel['to']}'),
                  value: _selected{rel['to']}Ids.isNotEmpty ? _selected{rel['to']}Ids.first : null,
                  items: snapshot.data!.map((e) => DropdownMenuItem(
                    value: e.{related_pk}.toString(),
                    child: Text(e.{display_attr}.toString()),
                  )).toList(),
                  onChanged: (v) {{
                    setState(() {{
                      if (v != null) {{
                        _selected{rel['to']}Ids = [v];
                      }} else {{
                        _selected{rel['to']}Ids = [];
                      }}
                    }});
                  }},
                );
              }},
            )""")

        # Generar creación del objeto
        # Para PKs numéricas: Si es creación, NO enviar (backend genera). Si es edición, enviar desde widget.item
        # Para PKs string: Siempre enviar desde el controlador
        create_object_fields_list = []
        for i, attr in enumerate(all_attributes):
            # Si es PK numérica (primer atributo y numérico)
            if i == 0 and is_numeric_pk and parent_class is None:
                # En edición, usar el PK del item existente. En creación, el backend lo genera
                create_object_fields_list.append(f"{attr['name']}: widget.item?.{attr['name']} ?? 0")
            else:
                # Para otros atributos, usar el valor del controlador
                create_object_fields_list.append(f"{attr['name']}: {self._parse_field_value(attr)}")
        
        create_object_fields = ',\n          '.join(create_object_fields_list)
        
        # Agregar relaciones many_to_one al objeto
        many_to_one_fields = []
        for rel in relationships:
            if rel["kind"] == "many_to_one":
                field_name = f"{self._to_snake_case(rel['to'])}Id"
                normalized_field = field_name.lower().replace('_', '')
                if normalized_field not in existing_attr_names_normalized:
                    many_to_one_fields.append(f"{field_name}: _selected{rel['to']}Id ?? ''")
        
        if many_to_one_fields:
            if create_object_fields:
                create_object_fields += ',\n          ' + ',\n          '.join(many_to_one_fields)
            else:
                create_object_fields = ',\n          '.join(many_to_one_fields)
        
        # Agregar relaciones al objeto (one_to_one, one_to_many)
        relation_fields = []
        for rel in relationships:
            if rel["kind"] == "one_to_one":
                field_name = self._to_snake_case(rel['to'])
                normalized_field = field_name.lower().replace('_', '')
                if normalized_field not in existing_attr_names_normalized:
                    # En lugar de crear un objeto vacío, obtener el objeto desde el servicio
                    relation_fields.append(f"{field_name}: await _get{rel['to']}ById(_selected{rel['to']}Id ?? '')")
            elif rel["kind"] == "one_to_many":
                # Mantener en singular
                field_name = self._to_snake_case(rel['to'])
                normalized_field = field_name.lower().replace('_', '')
                if normalized_field not in existing_attr_names_normalized:
                    # Obtener los objetos completos desde el servicio
                    relation_fields.append(f"{field_name}: await _get{rel['to']}sByIds(_selected{rel['to']}Ids)")
        
        if relation_fields:
            create_object_fields += ',\n          ' + ',\n          '.join(relation_fields)
        
        # Generar imports para modelos y servicios relacionados
        related_imports = []
        helper_services = set()  # Para rastrear qué servicios necesitan helpers
        helper_services_single = set()  # Para rastrear servicios que necesitan getById
        
        for rel in relationships:
            # Importar modelos para one_to_one y one_to_many
            if rel["kind"] in ["one_to_one", "one_to_many"]:
                related_imports.append(f"import '../models/{self._to_snake_case(rel['to'])}.dart';")
                related_imports.append(f"import '../services/{self._to_snake_case(rel['to'])}_service.dart';")
                if rel["kind"] == "one_to_many":
                    helper_services.add(rel['to'])
                elif rel["kind"] == "one_to_one":
                    helper_services_single.add(rel['to'])
            # Importar servicios para many_to_one (dropdowns)
            if rel["kind"] == "many_to_one":
                related_imports.append(f"import '../models/{self._to_snake_case(rel['to'])}.dart';")
                related_imports.append(f"import '../services/{self._to_snake_case(rel['to'])}_service.dart';")
        
        # Eliminar duplicados y ordenar
        related_imports = sorted(set(related_imports))
        related_imports_str = '\n'.join(related_imports) if related_imports else ''
        
        # Generar métodos helper para one_to_many
        helper_methods = []
        for service_name in helper_services:
            # Obtener la PK de la clase del servicio
            related_class = next((c for c in self.classes if c['name'] == service_name), None)
            
            def get_service_pk(class_name):
                current = next((c for c in self.classes if c['name'] == class_name), None)
                if current:
                    parent_rels = [r for r in self.parsed_relationships if r["from"] == class_name and r["kind"] == "inherits"]
                    if parent_rels:
                        return get_service_pk(parent_rels[0]["to"])
                    attrs = current.get('attributes', [])
                    if attrs:
                        return attrs[0]['name']
                return 'id'
            
            service_pk = get_service_pk(service_name)
            
            helper_methods.append(f"""
  Future<List<{service_name}>> _get{service_name}sByIds(List<String> ids) async {{
    final service = {service_name}Service();
    final allItems = await service.getAll();
    return allItems.where((item) => ids.contains(item.{service_pk}.toString())).toList();
  }}""")
        
        # Generar métodos helper para one_to_one
        for service_name in helper_services_single:
            helper_methods.append(f"""
  Future<{service_name}> _get{service_name}ById(String id) async {{
    final service = {service_name}Service();
    final item = await service.getById(id);
    if (item == null) {{
      throw Exception('{service_name} no encontrado');
    }}
    return item;
  }}""")
        
        content = f"""import 'package:flutter/material.dart';
import '../models/{snake_name}.dart';
import '../services/{snake_name}_service.dart';
{related_imports_str}

class {name}FormView extends StatefulWidget {{
  final {name}? item;

  const {name}FormView({{super.key, this.item}});

  @override
  State<{name}FormView> createState() => _{name}FormViewState();
}}

class _{name}FormViewState extends State<{name}FormView> {{
  final _formKey = GlobalKey<FormState>();
  final {name}Service _service = {name}Service();
  {controllers}
  bool _isLoading = false;

  @override
  void initState() {{
    super.initState();
    if (widget.item != null) {{
      {init_controllers}
    }}
  }}

  @override
  void dispose() {{
{self._generate_dispose_controllers(all_attributes, is_numeric_pk, parent_class)}
    super.dispose();
  }}

  Future<void> _submit() async {{
    if (!_formKey.currentState!.validate()) return;

    setState(() => _isLoading = true);

    try {{
      final item = {name}(
        {create_object_fields},
      );

      if (widget.item == null) {{
        await _service.create(item);
      }} else {{
        await _service.update(item.{pk_name}.toString(), item);
      }}

      if (mounted) {{
        Navigator.pop(context);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(widget.item == null
                ? 'Creado exitosamente'
                : 'Actualizado exitosamente'),
          ),
        );
      }}
    }} catch (e) {{
      setState(() => _isLoading = false);
      if (mounted) {{
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e')),
        );
      }}
    }}
  }}
{''.join(helper_methods)}

  @override
  Widget build(BuildContext context) {{
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.item == null ? 'Crear {name}' : 'Editar {name}'),
        backgroundColor: Theme.of(context).colorScheme.inversePrimary,
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : SingleChildScrollView(
              padding: const EdgeInsets.all(16),
              child: Form(
                key: _formKey,
                child: Column(
                  children: [
{','.join([chr(10) + '                    const SizedBox(height: 16),' + chr(10) + field for field in form_fields])},
                    const SizedBox(height: 24),
                    SizedBox(
                      width: double.infinity,
                      child: ElevatedButton(
                        onPressed: _submit,
                        style: ElevatedButton.styleFrom(
                          padding: const EdgeInsets.all(16),
                        ),
                        child: Text(
                          widget.item == null ? 'Crear' : 'Actualizar',
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
    );
  }}
}}
"""
        file_path = base_path / 'lib' / 'views' / f'{snake_name}_form_view.dart'
        file_path.write_text(content, encoding="utf-8", newline="\n")
    
    def _generate_detail_view(self, base_path, clase):
        """Genera la vista de detalle"""
        name = clase['name']
        snake_name = self._to_snake_case(name)
        relationships = [r for r in self.parsed_relationships if r["from"] == name]
        attributes = clase.get('attributes', [])
        
        # Detectar herencia y obtener todos los atributos
        parent_class = None
        for rel in relationships:
            if rel["kind"] == "inherits":
                parent_class = rel["to"]
                break
        
        # Función recursiva para obtener todos los atributos heredados
        def get_all_attributes(class_name):
            attrs = []
            current_class = next((c for c in self.classes if c['name'] == class_name), None)
            if current_class:
                # Primero obtener atributos del padre (si existe)
                parent_rels = [r for r in self.parsed_relationships if r["from"] == class_name and r["kind"] == "inherits"]
                if parent_rels:
                    parent_name = parent_rels[0]["to"]
                    attrs.extend(get_all_attributes(parent_name))
                # Luego agregar atributos propios
                attrs.extend(current_class.get('attributes', []))
            return attrs
        
        all_attributes = get_all_attributes(name)
        
        # El primer atributo es la PK
        pk_attr = all_attributes[0] if all_attributes else None
        pk_name = pk_attr['name'] if pk_attr else 'id'
        
        # Normalizar para evitar duplicados
        existing_attr_names_normalized = {attr['name'].lower().replace('_', '') for attr in all_attributes}
        
        # Generar filas de detalles - incluir todos los campos (incluyendo PK)
        detail_rows = []
        for attr in all_attributes:
            detail_rows.append(f"""              _buildDetailRow('{attr['name']}', item.{attr['name']}.toString())""")
        
        # Agregar relaciones
        for rel in relationships:
            if rel["kind"] == "one_to_many":
                # Mantener en singular
                field_name = self._to_snake_case(rel['to'])
                normalized_field = field_name.lower().replace('_', '')
                if normalized_field not in existing_attr_names_normalized:
                    # Obtener el primer atributo de la clase relacionada para mostrar
                    related_class = next((c for c in self.classes if c['name'] == rel['to']), None)
                    display_attr = 'id'
                    if related_class:
                        attrs = related_class.get('attributes', [])
                        # Buscar el primer atributo que no sea 'id'
                        for attr in attrs:
                            if attr['name'].lower() != 'id':
                                display_attr = attr['name']
                                break
                    
                    detail_rows.append(f"""              const SizedBox(height: 16),
              Text('{rel['to']}s:', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
              const SizedBox(height: 8),
              if (item.{field_name}.isEmpty)
                const Padding(
                  padding: EdgeInsets.only(left: 16, bottom: 4),
                  child: Text('No hay {rel['to'].lower()}s registrados', style: TextStyle(fontSize: 14, fontStyle: FontStyle.italic, color: Colors.grey)),
                )
              else
                ...item.{field_name}.map((e) => Padding(
                  padding: const EdgeInsets.only(left: 16, bottom: 4),
                  child: Text('• ${{e.{display_attr}.toString()}}', style: const TextStyle(fontSize: 14)),
                ))""")
            elif rel["kind"] == "one_to_one":
                field_name = self._to_snake_case(rel['to'])
                normalized_field = field_name.lower().replace('_', '')
                if normalized_field not in existing_attr_names_normalized:
                    # Obtener el primer atributo de la clase relacionada para mostrar
                    related_class = next((c for c in self.classes if c['name'] == rel['to']), None)
                    display_attr = 'id'
                    if related_class:
                        attrs = related_class.get('attributes', [])
                        # Buscar el primer atributo que no sea 'id'
                        for attr in attrs:
                            if attr['name'].lower() != 'id':
                                display_attr = attr['name']
                                break
                    
                    # Usar acceso condicional seguro con ?? para manejar null
                    detail_rows.append(f"""              _buildDetailRow('{rel['to']}', (item.{field_name}?.{display_attr} ?? 'N/A').toString())""")
        
        content = f"""import 'package:flutter/material.dart';
import '../models/{snake_name}.dart';

class {name}DetailView extends StatelessWidget {{
  final {name} item;

  const {name}DetailView({{super.key, required this.item}});

  @override
  Widget build(BuildContext context) {{
    return Scaffold(
      appBar: AppBar(
        title: const Text('Detalle de {name}'),
        backgroundColor: Theme.of(context).colorScheme.inversePrimary,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '{name}',
                  style: Theme.of(context).textTheme.headlineSmall,
                ),
                const Divider(height: 32),
{','.join([chr(10) + row + ',' + chr(10) + '                const SizedBox(height: 12)' for row in detail_rows])}
              ],
            ),
          ),
        ),
      ),
    );
  }}

  Widget _buildDetailRow(String label, String value) {{
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          width: 120,
          child: Text(
            '$label:',
            style: const TextStyle(
              fontWeight: FontWeight.bold,
              fontSize: 16,
            ),
          ),
        ),
        Expanded(
          child: Text(
            value,
            style: const TextStyle(fontSize: 16),
          ),
        ),
      ],
    );
  }}
}}
"""
        file_path = base_path / 'lib' / 'views' / f'{snake_name}_detail_view.dart'
        file_path.write_text(content, encoding="utf-8", newline="\n")
    
    def _generate_routes(self, base_path):
        """Genera el archivo de rutas (opcional)"""
        pass
    
    # Utilidades
    def _to_snake_case(self, name):
        """Convierte PascalCase a snake_case"""
        import re
        name = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', name).lower()
    
    def _to_backend_json_key(self, name):
        """Convierte nombre de atributo al formato del backend: minúsculas sin separadores"""
        # Eliminar guiones bajos y convertir a minúsculas
        return name.replace('_', '').lower()
    
    def _convert_type(self, uml_type):
        """Convierte tipos UML a tipos Dart"""
        type_map = {
            'string': 'String',
            'String': 'String',
            'int': 'int',
            'Int': 'int',
            'double': 'double',
            'Double': 'double',
            'bool': 'bool',
            'Boolean': 'bool',
            'Date': 'DateTime',
        }
        return type_map.get(uml_type, 'String')
    
    def _generate_copy_with_params(self, attributes):
        """Genera parámetros para copyWith"""
        params = []
        for attr in attributes:
            dart_type = self._convert_type(attr['type'])
            params.append(f"    {dart_type}? {attr['name']}")
        return ',\n'.join(params) + ',' if params else ''
    
    def _generate_copy_with_assignments(self, attributes):
        """Genera asignaciones para copyWith"""
        assignments = []
        for attr in attributes:
            assignments.append(f"      {attr['name']}: {attr['name']} ?? this.{attr['name']}")
        return ',\n'.join(assignments) + ',' if assignments else ''
    
    def _parse_field_value(self, attr):
        """Genera el código para parsear el valor del campo"""
        dart_type = self._convert_type(attr['type'])
        field_name = attr['name']
        
        if dart_type == 'int':
            return f"int.tryParse(_{field_name}Controller.text) ?? 0"
        elif dart_type == 'double':
            return f"double.tryParse(_{field_name}Controller.text) ?? 0.0"
        elif dart_type == 'bool':
            return f"_{field_name}Controller.text.toLowerCase() == 'true'"
        else:
            return f"_{field_name}Controller.text"


    def _sanitize(self, text: str) -> str:
        """Normaliza texto y elimina caracteres problemáticos."""
        text = unicodedata.normalize("NFC", text)
        # Reemplazar signos que a veces fallan en YAML
        text = (
            text.replace("¿", "?")
                .replace("¡", "!")
                .replace("“", '"')
                .replace("”", '"')
                .replace("‘", "'")
                .replace("’", "'")
        )
        return text

    def _generate_dispose_controllers(self, attributes, is_numeric_pk=False, parent_class=None):
        """Genera dispose para los controladores que realmente existen"""
        disposes = []
        for i, attr in enumerate(attributes):
            # Si es la PK (primer atributo) y es numérica y no hay herencia, NO hay controlador
            if i == 0 and is_numeric_pk and parent_class is None:
                continue
            disposes.append(f"    _{attr['name']}Controller.dispose();")
        return '\n'.join(disposes)

