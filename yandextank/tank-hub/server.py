import connexion


def get_app():
    app = connexion.App(__name__, specification_dir='./')
    app.add_api('api.yaml')
    return app.app
    # app.run(port=80)


application = get_app()
