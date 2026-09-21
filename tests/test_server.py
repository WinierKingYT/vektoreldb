def test_server_module_defines_app_factory() -> None:
    from personal_vector_db.server import create_production_app

    assert callable(create_production_app)
