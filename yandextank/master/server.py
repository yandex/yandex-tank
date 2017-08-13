import connexion

app = connexion.App(__name__, specification_dir='./')
app.add_api('api.yaml')
app.run(port=8080)