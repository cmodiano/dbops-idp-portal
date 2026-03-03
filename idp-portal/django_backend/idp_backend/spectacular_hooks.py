"""
Hooks drf-spectacular pour la documentation API.
"""


def postprocess_filter_empty_tags(result, generator, *, public=False, **kwargs):
    """
    En mode schéma public : supprime les tags qui n'ont aucune opération.
    Évite les sections vides dans le Swagger UI public.
    """
    if not public:
        return result

    # Collecter les tags utilisés dans les opérations
    used_tags = set()
    paths = result.get('paths', {})
    for path_item in paths.values():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method.lower() in ('get', 'post', 'put', 'patch', 'delete', 'head', 'options', 'trace'):
                if isinstance(operation, dict) and 'tags' in operation:
                    used_tags.update(operation['tags'])

    # Filtrer result['tags'] pour ne garder que les tags utilisés
    schema_tags = result.get('tags', [])
    if schema_tags and used_tags:
        filtered_tags = [t for t in schema_tags if isinstance(t, dict) and t.get('name') in used_tags]
        result['tags'] = filtered_tags

    return result
