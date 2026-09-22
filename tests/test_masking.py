from shared.logging import mask_dict

def test_masking_secrets():
    test_data = {
        "db_password": "super_secret_db",
        "jwt_secret": "super_secret_jwt",
        "naver_client_secret": "super_secret_naver",
        "admin_initial_password": "super_secret_admin",
        "nested": {
            "api_key": "some_api_key",
            "other": "safe"
        },
        "list_data": [
            {"credential": "some_credential"},
            {"safe_key": "safe_value"}
        ],
        "email": "user@example.com",
        "user_email": "admin@domain.com"
    }

    masked = mask_dict(test_data)

    assert masked["db_password"] == "***"
    assert masked["jwt_secret"] == "***"
    assert masked["naver_client_secret"] == "***"
    assert masked["admin_initial_password"] == "***"
    
    assert masked["nested"]["api_key"] == "***"
    assert masked["nested"]["other"] == "safe"
    
    assert masked["list_data"][0]["credential"] == "***"
    assert masked["list_data"][1]["safe_key"] == "safe_value"
    
    assert masked["email"] == "u***@example.com"
    assert masked["user_email"] == "a***@domain.com"
