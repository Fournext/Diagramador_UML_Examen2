package generator_uml.back_generator_uml.service;

import com.github.mustachejava.Mustache;
import com.github.mustachejava.MustacheFactory;
import generator_uml.back_generator_uml.entity.UmlClass;
import generator_uml.back_generator_uml.entity.UmlSchema;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.zeroturnaround.zip.ZipUtil;

import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class ProjectGenerator {

    private final MustacheFactory mustacheFactory;

    public Path generate(UmlSchema schema, String basePackage, String artifactId) throws Exception {
        Path root = Files.createTempDirectory("gen-" + artifactId);
        Path srcMain = root.resolve("src/main/java/" + basePackage.replace(".", "/"));
        Path srcRes = root.resolve("src/main/resources");
        Files.createDirectories(srcMain);
        Files.createDirectories(srcRes);

        // pom y Application
        render("pom.mustache", Map.of(
                "groupId", "com.example",
                "artifactId", artifactId,
                "basePackage", basePackage
        ), root.resolve("pom.xml"));

        render("Application.mustache", Map.of("basePackage", basePackage),
                srcMain.resolve("GenAppApplication.java"));

        // application.properties
        Map<String, Object> props = Map.of(
                "serverPort", 9000,
                "dbHost", "localhost",
                "dbPort", "5432",
                "dbName", "mi_base",
                "dbUser", "postgres",
                "dbPassword", "123456",
                "dbDriver", "org.postgresql.Driver",
                "dbDialect", "org.hibernate.dialect.PostgreSQLDialect"
        );
        render("application-properties.mustache", props, srcRes.resolve("application.properties"));

        // carpetas
        Path modelDir = srcMain.resolve("model");
        Path repoDir  = srcMain.resolve("repository");
        Path svcDir   = srcMain.resolve("service");
        Path ctrlDir  = srcMain.resolve("controller");
        Files.createDirectories(modelDir);
        Files.createDirectories(repoDir);
        Files.createDirectories(svcDir);
        Files.createDirectories(ctrlDir);

        // normalizar
        schema = JsonNormalizer.normalize(schema);

        for (UmlClass c : schema.getClasses()) {
            String entityName = NamingUtil.toJavaClass(c.getName());

            // ====== DETECTAR PADRE (herencia) ANTES ======
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
            boolean isChild = parentClass != null;

            // ====== ATRIBUTOS (PK dinámica: num -> Long autoinc, String -> PK sin autoinc) ======
            List<Map<String, Object>> attrs = new ArrayList<>();
            boolean pkAssigned = false;
            String pkName = null;
            String pkType = null;

            for (var attr : c.getAttributes()) {
                Map<String, Object> a = new HashMap<>();
                String type = TypeMapper.toJava(attr.getType());
                String name = NamingUtil.toField(attr.getName());

                boolean isNumeric = type.equalsIgnoreCase("int")
                        || type.equalsIgnoreCase("Integer")
                        || type.equalsIgnoreCase("long")
                        || type.equalsIgnoreCase("Long")
                        || type.equalsIgnoreCase("short")
                        || type.equalsIgnoreCase("byte");

                if (!isChild && !pkAssigned) {
                    if (isNumeric) {
                        a.put("isId", true);
                        a.put("type", "Long");
                        a.put("generated", true);
                        pkAssigned = true;
                        pkName = name;
                        pkType = "Long";
                    } else if (type.equalsIgnoreCase("String")
                            || type.equalsIgnoreCase("char")
                            || type.equalsIgnoreCase("Character")) {
                        a.put("isId", true);
                        a.put("type", "String");
                        a.put("generated", false);
                        pkAssigned = true;
                        pkName = name;
                        pkType = "String";
                    } else {
                        a.put("isId", false);
                        a.put("type", type);
                    }
                } else {
                    a.put("isId", false);
                    a.put("type", type);
                }
                a.put("name", name);
                attrs.add(a);
            }

            // ====== RELACIONES ======
            List<Map<String, Object>> oneToMany = new ArrayList<>();
            List<Map<String, Object>> manyToOne = new ArrayList<>();
            List<Map<String, Object>> oneToOne  = new ArrayList<>();
            List<Map<String, Object>> manyToMany = new ArrayList<>();
            boolean needsOnDeleteImport = false;

            // Para eliminar atributos ‘xxxId’ redundantes si hay relación
            Set<String> fkPlaceholderNames = new HashSet<>();

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

                    String sourceEntity = NamingUtil.toJavaClass(sourceName);
                    String targetEntity = NamingUtil.toJavaClass(targetName);

                    if ("generalization".equals(rel.getType()) && rel.getSourceId().equals(c.getId())) {
                        parentClass = targetEntity;
                    }

                    // ---- Asociaciones / Agregación / Composición / Dependencia ----
                    if ("association".equals(rel.getType())
                            || "aggregation".equals(rel.getType())
                            || "composition".equals(rel.getType())
                            || "dependency".equals(rel.getType())) {

                        // 1) Normalizar etiquetas (vacías -> "1")
                        String rawSource = (rel.getLabels().size() > 0 && rel.getLabels().get(0) != null)
                                ? rel.getLabels().get(0).trim()
                                : "";
                        String rawTarget = (rel.getLabels().size() > 1 && rel.getLabels().get(1) != null)
                                ? rel.getLabels().get(1).trim()
                                : "";

                        String sourceCard = rawSource.isEmpty() ? "*" : rawSource;
                        String targetCard = rawTarget.isEmpty() ? "1" : rawTarget;

                        // 2) Regla por defecto para dependency SIN multiplicidades (o vacías)
                        if ("dependency".equals(rel.getType())) {
                            boolean noMultis = (rawSource.isEmpty() && rawTarget.isEmpty());
                            if (noMultis) {
                                // por defecto: muchos dependientes (*)
                                // apuntan a un principal (1)
                                sourceCard = "*";
                                targetCard = "1";
                            }
                        }

                        // 3) Detectar "many"
                        boolean sourceIsMany = sourceCard.contains("*");
                        boolean targetIsMany = targetCard.contains("*");

                        // (opcional) tipo PK target, si lo necesitas
                        UmlClass targetClassObj = schema.getClasses().stream()
                                .filter(pc -> pc.getName().equals(targetName))
                                .findFirst().orElse(null);
                        String targetPkType = "Long";
                        if (targetClassObj != null && !targetClassObj.getAttributes().isEmpty()) {
                            targetPkType = TypeMapper.toJava(targetClassObj.getAttributes().get(0).getType());
                        }
                        // 👇 Nuevo: nunca dejes que dependency sea tratado como 1..1
                        if ("dependency".equals(rel.getType()) && !sourceIsMany && !targetIsMany) {
                            sourceIsMany = true;
                            targetIsMany = false;
                        }


                        // === Lado SOURCE = esta clase ===
                        if (c.getName().equals(sourceName)) {
                            if (!sourceIsMany && targetIsMany) {
                                // 1..* => OneToMany en source
                                oneToMany.add(Map.of(
                                        "TargetEntity", targetEntity,
                                        "collectionField", NamingUtil.plural(NamingUtil.toField(targetEntity)),
                                        "mappedBy", NamingUtil.toField(sourceEntity)
                                ));
                            } else if (!sourceIsMany && !targetIsMany) {
                                // 1..1 => OneToOne
                                boolean isComposition = "composition".equals(rel.getType());
                                oneToOne.add(Map.of(
                                        "TargetEntity", targetEntity,
                                        "targetField", NamingUtil.toField(targetEntity),
                                        "composition", isComposition
                                ));
                                if (isComposition) {
                                    needsOnDeleteImport = true;
                                }
                            } else if (sourceIsMany && targetIsMany) {
                                // *..* => ManyToMany
                                manyToMany.add(Map.of(
                                        "TargetEntity", targetEntity,
                                        "collectionField", NamingUtil.plural(NamingUtil.toField(targetEntity)),
                                        "joinTable", sourceEntity.toLowerCase() + "_" + targetEntity.toLowerCase(),
                                        "thisTable", sourceEntity.toLowerCase(),
                                        "otherTable", targetEntity.toLowerCase()
                                ));
                            } else if (sourceIsMany && !targetIsMany) {
                                // *..1 => ManyToOne
                                manyToOne.add(Map.of(
                                        "TargetEntity", targetEntity,
                                        "targetField", NamingUtil.toField(targetEntity)
                                ));
                            }
                        }

                        // === Lado TARGET = esta clase (inversos) ===
                        if (c.getName().equals(targetName)) {
                            if (targetIsMany && !sourceIsMany) {
                                // 1..* => ManyToOne en target hacia source
                                manyToOne.add(Map.of(
                                        "TargetEntity", sourceEntity,
                                        "targetField", NamingUtil.toField(sourceEntity)
                                ));
                            } else if (!targetIsMany && sourceIsMany) {
                                // *..1 => OneToMany en target
                                oneToMany.add(Map.of(
                                        "TargetEntity", sourceEntity,
                                        "collectionField", NamingUtil.plural(NamingUtil.toField(sourceEntity)),
                                        "mappedBy", NamingUtil.toField(targetEntity)
                                ));
                            }
                            // 1..1 y *..* no se duplican si ya lo generaste en source
                        }
                    }
                }

                // Si la clase hereda de otra, eliminar atributos duplicados del padre
                if (parentClass != null) {
                    final String parentClassName = parentClass;
                    UmlClass parent = schema.getClasses().stream()
                            .filter(pc -> NamingUtil.toJavaClass(pc.getName()).equals(parentClassName))
                            .findFirst()
                            .orElse(null);

                    if (parent != null) {
                        final Set<String> parentAttrs = parent.getAttributes().stream()
                                .map(a -> NamingUtil.toField(a.getName()))
                                .collect(Collectors.toSet());

                        attrs.removeIf(a -> parentAttrs.contains((String) a.get("name")));
                    }
                }
            }

            // ====== ELIMINAR placeholders “xxxId” si hubo relaciones que los sustituyen ======
            if (!fkPlaceholderNames.isEmpty()) {
                attrs.removeIf(a -> fkPlaceholderNames.contains(((String) a.get("name")).toLowerCase()));
            }

            // ====== MÉTODOS VACÍOS ======
            List<Map<String, Object>> methods = new ArrayList<>();
            for (var m : c.getMethods()) {
                Map<String, Object> mm = new HashMap<>();
                String returnType = (m.getReturnType() == null || m.getReturnType().isBlank()) ? "void" : TypeMapper.toJava(m.getReturnType());
                mm.put("name", m.getName());
                mm.put("parameters", m.getParameters() == null ? "" : m.getParameters());
                mm.put("returnType", returnType);

                String defaultReturn = switch (returnType) {
                    case "int", "long", "short", "byte" -> "0";
                    case "double", "float" -> "0.0";
                    case "boolean" -> "false";
                    case "char" -> "'\\u0000'";
                    default -> "null";
                };
                mm.put("defaultReturn", defaultReturn);
                methods.add(mm);
            }

            boolean isParent = schema.getRelationships().stream()
                    .anyMatch(r -> "generalization".equals(r.getType()) && r.getTargetId().equals(c.getId()));

            // ====== CONTEXTO MUSTACHE ======
            Map<String, Object> entityCtx = new HashMap<>();
            entityCtx.put("basePackage", basePackage);
            entityCtx.put("EntityName", entityName);
            entityCtx.put("attributes", attrs);
            entityCtx.put("oneToMany", oneToMany);
            entityCtx.put("manyToOne", manyToOne);
            entityCtx.put("oneToOne", oneToOne);
            entityCtx.put("manyToMany", manyToMany);
            entityCtx.put("parentClass", parentClass);
            entityCtx.put("methods", methods);
            entityCtx.put("isParent", isParent);
            entityCtx.put("plural", entityName.toLowerCase());
            entityCtx.put("needsOnDeleteImport", needsOnDeleteImport);

            // PK para Controller/Service
            if (isChild) {
                final String parentClassName = parentClass;
                UmlClass parent = schema.getClasses().stream()
                        .filter(pc -> NamingUtil.toJavaClass(pc.getName()).equals(parentClassName))
                        .findFirst()
                        .orElse(null);

                if (parent != null && !parent.getAttributes().isEmpty()) {
                    String parentPkName = NamingUtil.toField(parent.getAttributes().get(0).getName());
                    String parentPkType = TypeMapper.toJava(parent.getAttributes().get(0).getType());
                    String pkSetter = "set" + Character.toUpperCase(parentPkName.charAt(0)) + parentPkName.substring(1);

                    entityCtx.put("pkName", parentPkName);
                    entityCtx.put("pkType", parentPkType);
                    entityCtx.put("pkSetter", pkSetter);
                    entityCtx.put("hasPk", true);
                } else {
                    entityCtx.put("hasPk", false);
                }
            } else if (pkAssigned) {
                String pkSetter = "set" + Character.toUpperCase(pkName.charAt(0)) + pkName.substring(1);
                entityCtx.put("pkName", pkName);
                entityCtx.put("pkType", pkType);
                entityCtx.put("pkSetter", pkSetter);
                entityCtx.put("hasPk", true);
            } else {
                entityCtx.put("hasPk", false);
            }

            // render
            render("Entity.mustache", entityCtx, modelDir.resolve(entityName + ".java"));
            render("Repository.mustache", entityCtx, repoDir.resolve(entityName + "Repository.java"));
            render("Service.mustache", entityCtx, svcDir.resolve(entityName + "Service.java"));
            render("Controller.mustache", entityCtx, ctrlDir.resolve(entityName + "Controller.java"));
        }

        Path zip = root.getParent().resolve(artifactId + ".zip");
        ZipUtil.pack(root.toFile(), zip.toFile());
        return zip;
    }

    private void render(String template, Map<String, Object> ctx, Path target) throws IOException {
        Mustache mustache = mustacheFactory.compile("templates/" + template);
        try (Writer w = new FileWriter(target.toFile())) {
            mustache.execute(w, ctx).flush();
        }
    }
}
