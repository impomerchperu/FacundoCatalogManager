import requests

URL = "https://stock.importacionesfacundo.com/wp-admin/admin-ajax.php"


payload = {
    "action": "jet_smart_filters",
    "provider": "bricks-query-loop/querydesk",
    # Query
    "query[post_type][]": "product",
    "query[orderby][menu_order]": "ASC",
    "query[posts_per_page]": "25",
    "query[post_status]": "publish",
    "query[paged]": "1",
    # Defaults
    "defaults[disable_query_merge]": "true",
    "defaults[post_type][]": "product",
    "defaults[posts_per_page]": "25",
    "defaults[post_status]": "publish",
    "defaults[paged]": "1",
    # Settings
    "settings[filtered_post_id]": "134",
    "settings[element_id]": "95dc8a",
    "settings[is_archive_main_query]": "true",
    "settings[jsf_signature]": "09ae640be37958cc0b229a8b7a47393e",
    # Props
    "props[found_posts]": "19",
    "props[max_num_pages]": "1",
    "props[page]": "1",
}


headers = {
    "User-Agent": ("Mozilla/5.0 Windows Chrome"),
    "Referer": (
        "https://stock.importacionesfacundo.com/categoria-producto/jarros-mug/"
    ),
}


response = requests.post(URL, data=payload, headers=headers, timeout=30)


print("=" * 60)
print("STATUS")
print("=" * 60)

print(response.status_code)


print()
print("=" * 60)
print("RESPUESTA")
print("=" * 60)

print(response.text[:3000])
