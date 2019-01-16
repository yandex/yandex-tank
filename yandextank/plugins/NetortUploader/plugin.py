from yandextank.common.interfaces import AbstractPlugin, AggregateResultListener


class Plugin(AbstractPlugin, AggregateResultListener):
    SECTION = 'nuploader'
    def __init__(self, core, cfg, name):
        super(Plugin, self).__init__(core, cfg, name)

    def configure(self):
        self.core.job.subscribe_plugin(self)

    def on_aggregated_data(self, data, stats):
        """
        @data: aggregated data
        @stats: stats about gun
        """
        self.data_and_stats_stream.write(
            '%s\n' % json.dumps({
                'data': data,
                'stats': stats
            }))