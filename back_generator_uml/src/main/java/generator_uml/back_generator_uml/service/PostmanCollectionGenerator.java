package generator_uml.back_generator_uml.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.*;
import generator_uml.back_generator_uml.entity.*;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;

@Service
public class PostmanCollectionGenerator {

    private final ObjectMapper objectMapper = new ObjectMapper();

    public Path generatePostmanCollection(UmlSchema schema, String baseUrl, String artifactId) throws IOException {
        schema = JsonNormalizer.normalize(schema);

        ObjectNode collection = objectMapper.createObjectNode();
        ObjectNode info = collection.putObject("info");
        info.put("name", artifactId + " API Collection");
        info.put("description", "Colección generada automáticamente para " + artifactId);
        info.put("schema", "https://schema.getpostman.com/json/collection/v2.1.0/collection.json");

        // ✅ variable de entorno baseUrl
        ArrayNode variable = collection.putArray("variable");
        ObjectNode baseVar = variable.addObject();
        baseVar.put("key", "baseUrl");
        baseVar.put("value", baseUrl);
        baseVar.put("type", "string");

        ArrayNode items = collection.putArray("item");

        for (UmlClass c : schema.getClasses()) {
            String entityName = NamingUtil.toJavaClass(c.getName());
            String pluralName = entityName.toLowerCase();

            ObjectNode folder = objectMapper.createObjectNode();
            folder.put("name", entityName);
            ArrayNode folderItems = folder.putArray("item");

            // Detectar PK considerando herencia
            String pkType = "String";
            String pkName = "id";
            
            // Detectar si tiene padre (herencia)
            final String[] parentClassNameHolder = {null};
            for (var rel : schema.getRelationships()) {
                if ("generalization".equals(rel.getType()) && rel.getSourceId().equals(c.getId())) {
                    parentClassNameHolder[0] = schema.getClasses().stream()
                            .filter(pc -> pc.getId().equals(rel.getTargetId()))
                            .map(UmlClass::getName)
                            .findFirst().orElse(null);
                    break;
                }
            }
            
            // Si tiene padre, buscar PK en el padre
            if (parentClassNameHolder[0] != null) {
                final String parentClassName = parentClassNameHolder[0];
                UmlClass parent = schema.getClasses().stream()
                        .filter(pc -> pc.getName().equals(parentClassName))
                        .findFirst().orElse(null);
                
                if (parent != null && !parent.getAttributes().isEmpty()) {
                    // El primer atributo del padre es la PK
                    pkName = NamingUtil.toField(parent.getAttributes().get(0).getName());
                    pkType = TypeMapper.toJava(parent.getAttributes().get(0).getType());
                }
            } else if (!c.getAttributes().isEmpty()) {
                // Si NO tiene padre, el primer atributo es la PK
                pkName = NamingUtil.toField(c.getAttributes().get(0).getName());
                pkType = TypeMapper.toJava(c.getAttributes().get(0).getType());
            }

            // GET All
            folderItems.add(createGetAllRequest(entityName, pluralName));

            // GET One
            folderItems.add(createGetOneRequest(entityName, pluralName, pkType));

            // POST Create
            folderItems.add(createPostRequest(entityName, pluralName, c, schema));


            // PUT Update
            folderItems.add(createPutRequest(entityName, pluralName, c, schema, pkType, pkName));

            // DELETE
            folderItems.add(createDeleteRequest(entityName, pluralName, pkType));

            items.add(folder);
        }

        Path outputPath = Files.createTempFile(artifactId + "-postman-", ".json");
        objectMapper.writerWithDefaultPrettyPrinter().writeValue(outputPath.toFile(), collection);
        return outputPath;
    }

    // =====================================
    // ============ REQUESTS ===============
    // =====================================

    private ObjectNode createGetAllRequest(String entityName, String pluralName) {
        ObjectNode request = objectMapper.createObjectNode();
        request.put("name", "Get All " + entityName);

        ObjectNode requestDetails = request.putObject("request");
        requestDetails.put("method", "GET");

        ObjectNode url = requestDetails.putObject("url");
        url.put("raw", "{{baseUrl}}/api/" + pluralName);
        ArrayNode host = url.putArray("host");
        host.add("{{baseUrl}}");
        ArrayNode path = url.putArray("path");
        path.add("api").add(pluralName);

        return request;
    }

    private ObjectNode createGetOneRequest(String entityName, String pluralName, String pkType) {
        ObjectNode request = objectMapper.createObjectNode();
        request.put("name", "Get One " + entityName);

        ObjectNode requestDetails = request.putObject("request");
        requestDetails.put("method", "GET");

        String exampleId = pkType.equals("String") ? "example-id" : "1";
        ObjectNode url = requestDetails.putObject("url");
        url.put("raw", "{{baseUrl}}/api/" + pluralName + "/" + exampleId);
        ArrayNode host = url.putArray("host");
        host.add("{{baseUrl}}");
        ArrayNode path = url.putArray("path");
        path.add("api").add(pluralName).add(exampleId);

        return request;
    }

    private ObjectNode createPostRequest(String entityName, String pluralName,
                                         UmlClass c, UmlSchema schema) {
        ObjectNode request = objectMapper.createObjectNode();
        request.put("name", "Create " + entityName);

        ObjectNode requestDetails = request.putObject("request");
        requestDetails.put("method", "POST");

        ArrayNode headers = requestDetails.putArray("header");
        headers.add(header("Content-Type", "application/json"));
        headers.add(header("Accept", "application/json"));

        ObjectNode body = requestDetails.putObject("body");
        body.put("mode", "raw");
        body.put("raw", generateSampleBody(c, schema, shouldIncludeIdInPost(c)));

        ObjectNode url = requestDetails.putObject("url");
        url.put("raw", "{{baseUrl}}/api/" + pluralName);
        ArrayNode host = url.putArray("host");
        host.add("{{baseUrl}}");
        ArrayNode path = url.putArray("path");
        path.add("api").add(pluralName);

        return request;
    }

    private ObjectNode createPutRequest(String entityName, String pluralName,
                                        UmlClass c, UmlSchema schema, String pkType, String pkName) {
        ObjectNode request = objectMapper.createObjectNode();
        request.put("name", "Update " + entityName);

        ObjectNode requestDetails = request.putObject("request");
        requestDetails.put("method", "PUT");

        ArrayNode headers = requestDetails.putArray("header");
        headers.add(header("Content-Type", "application/json"));
        headers.add(header("Accept", "application/json"));

        ObjectNode body = requestDetails.putObject("body");
        body.put("mode", "raw");
        body.put("raw", generateSampleBody(c, schema, false));

        String exampleId = pkType.equals("String") ? "example-id" : "1";
        ObjectNode url = requestDetails.putObject("url");
        url.put("raw", "{{baseUrl}}/api/" + pluralName + "/" + exampleId);
        ArrayNode host = url.putArray("host");
        host.add("{{baseUrl}}");
        ArrayNode path = url.putArray("path");
        path.add("api").add(pluralName).add(exampleId);

        return request;
    }

    private ObjectNode createDeleteRequest(String entityName, String pluralName, String pkType) {
        ObjectNode request = objectMapper.createObjectNode();
        request.put("name", "Delete " + entityName);

        ObjectNode requestDetails = request.putObject("request");
        requestDetails.put("method", "DELETE");

        String exampleId = pkType.equals("String") ? "example-id" : "1";
        ObjectNode url = requestDetails.putObject("url");
        url.put("raw", "{{baseUrl}}/api/" + pluralName + "/" + exampleId);
        ArrayNode host = url.putArray("host");
        host.add("{{baseUrl}}");
        ArrayNode path = url.putArray("path");
        path.add("api").add(pluralName).add(exampleId);

        return request;
    }

    private ObjectNode header(String key, String value) {
        ObjectNode h = objectMapper.createObjectNode();
        h.put("key", key);
        h.put("value", value);
        return h;
    }

    // =====================================
    // ============ BODY BUILDER ===========
    // =====================================

    private String generateSampleBody(UmlClass c, UmlSchema schema, boolean includeId) {
        ObjectNode body = objectMapper.createObjectNode();

        // Detectar si tiene padre (herencia)
        String parentClass = null;
        if (schema.getRelationships() != null) {
            for (var rel : schema.getRelationships()) {
                if ("generalization".equals(rel.getType()) && rel.getSourceId().equals(c.getId())) {
                    parentClass = schema.getClasses().stream()
                            .filter(pc -> pc.getId().equals(rel.getTargetId()))
                            .map(UmlClass::getName)
                            .map(NamingUtil::toJavaClass)
                            .findFirst()
                            .orElse(null);
                }
            }
        }

        // Atributos del padre (si hay herencia)
        if (parentClass != null) {
            String finalParentClass = parentClass;
            UmlClass parent = schema.getClasses().stream()
                    .filter(pc -> NamingUtil.toJavaClass(pc.getName()).equals(finalParentClass))
                    .findFirst().orElse(null);

            if (parent != null) {
                for (int i = 0; i < parent.getAttributes().size(); i++) {
                    var attr = parent.getAttributes().get(i);
                    String fieldName = NamingUtil.toField(attr.getName());
                    String type = TypeMapper.toJava(attr.getType());

                    // El primer atributo del padre es la PK
                    // Solo incluirlo si includeId es true
                    if (i == 0 && !includeId) {
                        continue;
                    }

                    body.set(fieldName, generateSampleValue(type, fieldName));
                }
            }
        }

        // Atributos propios de la clase
        // Si tiene padre, NINGUNO de estos es PK
        // Si NO tiene padre, el primero es PK
        for (int i = 0; i < c.getAttributes().size(); i++) {
            var attr = c.getAttributes().get(i);
            String fieldName = NamingUtil.toField(attr.getName());
            String type = TypeMapper.toJava(attr.getType());

            // Si NO tiene padre y es el primer atributo, es la PK
            if (parentClass == null && i == 0 && !includeId) {
                continue;
            }

            body.set(fieldName, generateSampleValue(type, fieldName));
        }

        // Relaciones ManyToOne o OneToOne: incluir objeto con ID
        if (schema.getRelationships() != null) {
            for (var rel : schema.getRelationships()) {
                String sourceName = schema.getClasses().stream()
                        .filter(cl -> cl.getId().equals(rel.getSourceId()))
                        .map(UmlClass::getName)
                        .findFirst().orElse(null);

                String targetName = schema.getClasses().stream()
                        .filter(cl -> cl.getId().equals(rel.getTargetId()))
                        .map(UmlClass::getName)
                        .findFirst().orElse(null);

                if (sourceName == null || targetName == null) continue;

                String sourceCard = rel.getLabels().size() > 0 ? rel.getLabels().get(0).trim() : "";
                String targetCard = rel.getLabels().size() > 1 ? rel.getLabels().get(1).trim() : "";

                if ("dependency".equals(rel.getType()) && sourceCard.isEmpty() && targetCard.isEmpty()) {
                    sourceCard = "*";
                    targetCard = "1";
                }

                boolean sourceIsMany = sourceCard.contains("*");
                boolean targetIsMany = targetCard.contains("*");

                if (c.getName().equals(sourceName) &&
                        ("association".equals(rel.getType()) ||
                                "aggregation".equals(rel.getType()) ||
                                "composition".equals(rel.getType()) ||
                                "dependency".equals(rel.getType()))) {

                    // Si source tiene cardinalidad * hacia target
                    // entonces Source tiene ManyToOne → incluir FK
                    if (sourceIsMany && !targetIsMany) {
                        String targetEntity = NamingUtil.toJavaClass(targetName);
                        String fieldName = NamingUtil.toField(targetEntity);

                        UmlClass targetClass = schema.getClasses().stream()
                                .filter(tc -> tc.getName().equals(targetName))
                                .findFirst().orElse(null);

                        if (targetClass != null && !targetClass.getAttributes().isEmpty()) {
                            String targetPkType = TypeMapper.toJava(targetClass.getAttributes().get(0).getType());
                            ObjectNode relObj = objectMapper.createObjectNode();
                            String pkFieldName = NamingUtil.toField(targetClass.getAttributes().get(0).getName());
                            relObj.set(pkFieldName, generateSampleValue(targetPkType, pkFieldName));
                            body.set(fieldName, relObj);
                        }
                    }
                    // Si source tiene cardinalidad 1 y target tiene 1 (OneToOne o Composition)
                    else if (!sourceIsMany && !targetIsMany) {
                        String targetEntity = NamingUtil.toJavaClass(targetName);
                        String fieldName = NamingUtil.toField(targetEntity);

                        UmlClass targetClass = schema.getClasses().stream()
                                .filter(tc -> tc.getName().equals(targetName))
                                .findFirst().orElse(null);

                        if (targetClass != null && !targetClass.getAttributes().isEmpty()) {
                            String targetPkType = TypeMapper.toJava(targetClass.getAttributes().get(0).getType());
                            ObjectNode relObj = objectMapper.createObjectNode();
                            String pkFieldName = NamingUtil.toField(targetClass.getAttributes().get(0).getName());
                            relObj.set(pkFieldName, generateSampleValue(targetPkType, pkFieldName));
                            body.set(fieldName, relObj);
                        }
                    }
                    // Si source=1 y target=many → Source tiene OneToMany, no incluir FK
                    // Si source=many y target=many → ManyToMany, no incluir FK en body simple
                }
                
                // Lado TARGET: si target tiene cardinalidad many y source tiene 1
                // entonces Target tiene ManyToOne hacia Source
                if (c.getName().equals(targetName) &&
                        ("association".equals(rel.getType()) ||
                                "aggregation".equals(rel.getType()) ||
                                "composition".equals(rel.getType()) ||
                                "dependency".equals(rel.getType()))) {

                    if (targetIsMany && !sourceIsMany) {
                        // Target (este objeto) tiene ManyToOne hacia Source
                        String sourceEntity = NamingUtil.toJavaClass(sourceName);
                        String fieldName = NamingUtil.toField(sourceEntity);

                        UmlClass sourceClass = schema.getClasses().stream()
                                .filter(sc -> sc.getName().equals(sourceName))
                                .findFirst().orElse(null);

                        if (sourceClass != null && !sourceClass.getAttributes().isEmpty()) {
                            String sourcePkType = TypeMapper.toJava(sourceClass.getAttributes().get(0).getType());
                            ObjectNode relObj = objectMapper.createObjectNode();
                            String pkFieldName = NamingUtil.toField(sourceClass.getAttributes().get(0).getName());
                            relObj.set(pkFieldName, generateSampleValue(sourcePkType, pkFieldName));
                            body.set(fieldName, relObj);
                        }
                    }
                }
            }
        }

        try {
            return objectMapper.writerWithDefaultPrettyPrinter().writeValueAsString(body);
        } catch (Exception e) {
            return "{}";
        }
    }

    // =====================================
    // ============ HELPERS ================
    // =====================================

    private JsonNode generateSampleValue(String type, String fieldName) {
        return switch (type) {
            case "Integer", "Long" -> {
                if (fieldName.toLowerCase().contains("id")) yield objectMapper.valueToTree(1);
                yield objectMapper.valueToTree(100);
            }
            case "Double", "Float" -> objectMapper.valueToTree(99.99);
            case "Boolean" -> objectMapper.valueToTree(true);
            case "String" -> {
                if (fieldName.toLowerCase().contains("name") || fieldName.toLowerCase().contains("nombre"))
                    yield objectMapper.valueToTree("Nombre Ejemplo");
                if (fieldName.toLowerCase().contains("email") || fieldName.toLowerCase().contains("correo"))
                    yield objectMapper.valueToTree("ejemplo@email.com");
                if (fieldName.toLowerCase().contains("phone") || fieldName.toLowerCase().contains("telefono"))
                    yield objectMapper.valueToTree("123456789");
                if (fieldName.toLowerCase().contains("address") || fieldName.toLowerCase().contains("direccion"))
                    yield objectMapper.valueToTree("Calle Ejemplo 123");
                if (fieldName.toLowerCase().contains("id"))
                    yield objectMapper.valueToTree("id-ejemplo-123");
                yield objectMapper.valueToTree("Valor de ejemplo");
            }
            default -> objectMapper.valueToTree("Valor de ejemplo");
        };
    }

    private boolean isNumericType(String javaType) {
        return javaType.equalsIgnoreCase("int") || javaType.equalsIgnoreCase("Integer")
                || javaType.equalsIgnoreCase("long") || javaType.equalsIgnoreCase("Long")
                || javaType.equalsIgnoreCase("short") || javaType.equalsIgnoreCase("byte");
    }

    private boolean shouldIncludeIdInPost(UmlClass c) {
        // El primer atributo de la clase (o del padre si tiene herencia) es la PK
        // Si es numérica → autogenerada → NO incluir en POST
        // Si es String → manual → SÍ incluir en POST
        
        String pkType = "String";
        
        // Buscar el primer atributo (si no tiene atributos, asumir autogenerada)
        if (!c.getAttributes().isEmpty()) {
            pkType = TypeMapper.toJava(c.getAttributes().get(0).getType());
        }
        
        return !isNumericType(pkType);
    }
}
