setup_t module_setup = setup_module_t {
	dir = "$phantom_modules_path"   
	list = {
	    io_monitor
		io_benchmark
		io_benchmark_method_stream
		io_benchmark_method_stream_ipv4
		io_benchmark_method_stream_ipv6
		io_benchmark_method_stream_source_log
		io_benchmark_method_stream_proto_none
		io_benchmark_method_stream_proto_http
		
		$additional_libs
	}
}

scheduler_t main_scheduler = scheduler_simple_t {	
	threads = $threads   
	event_buf_size = 20   
	timeout_prec = 1
}

logger_t phantom_logger = logger_file_t {
        filename = "$phantom_log"
        level = info
        scheduler = main_scheduler
}

logger = phantom_logger

$benchmarks_block

setup_t stat_setup = setup_stat_t {
        list = { default }
}


io_t monitor_io = io_monitor_t {
        list = { main_scheduler benchmark_io $stat_benchmarks }
        stat_id = default

        period = 1s
        clear = true

        scheduler = main_scheduler
        filename = "$stat_log"
}
