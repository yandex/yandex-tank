## Сборка porto-слоя с JDK и gatling.conf

Данный слой используется в тасклет-агенте, необходим для работы генератора нагрузки Gatling.

Чтобы собрать слой и загрузить его в Sandbox необходимо выполнить команды:

```bash
ya package -r -O /tmp/ --target-platform default-linux-x86_64 ~/arcadia/load/projects/yandex-tank/contrib/gatling/package.json

ya upload /tmp/load-testing-gatling.package_version.tar.gz --type PORTO_LAYER --description "JDK with gatling.conf" --attr ttl=inf
```

После загрузки слоя необходимо подменить ID получившегося ресурса в [спецификации тасклета](https://a.yandex-team.ru/arcadia/load/projects/tasklets/ulta/t.yaml) и запустить релиз тасклета.
