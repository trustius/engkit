def truncate(text, limit):
    return text if len(text) <= limit else text[:limit]
