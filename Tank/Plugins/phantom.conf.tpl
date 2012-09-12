setup_t module_setup = setup_module_t {
	dir = "/usr/lib/phantom"   
	list = {
		ssl
		io_benchmark
		io_benchmark_method_stream
		io_benchmark_method_stream_ipv4
		io_benchmark_method_stream_ipv6
		io_benchmark_method_stream_transport_ssl
		io_benchmark_method_stream_source_log
		io_benchmark_method_stream_proto_none
		io_benchmark_method_stream_proto_http
	}
}

scheduler_t main_scheduler = scheduler_simple_t {	
	threads = $threads   
	event_buf_size = 20   
	timeout_prec = 1
}

io_t benchmark_io = io_benchmark_t {
	method_t stream_method = $method_stream {
		logger_t benchmark_logger = logger_default_t {
			filename = "$answ_log"
			$comment_answ level = $answ_log_level
			scheduler = main_scheduler     
		}
	
	    logger_t brief_logger = logger_brief_t {
		  filename = "$phout"
		  time_format = unix       
		  scheduler = main_scheduler     
	    }
		
	    loggers = { 
		brief_logger 
		$comment_answ benchmark_logger 
	    }
	
	    source_t source_log = source_log_t {
			filename = "$stpd"     
	    }
	
	    $ssl_transport
	    
		proto_t http_proto = proto_http_t { 
			$reply_limits
		}
		
	    proto_t none_proto = proto_none_t { 
	    }
	    
	    proto=$proto
	    
	    address = $ip
	    port = $port
	    $bind
	    timeout = $timeout
	    source = source_log   
	}
	method = stream_method   
    
    times_t simple_times = times_simple_t {
                max = $timeout
                min = 1
                steps = 20
    }
	times = simple_times
    
	instances = $instances   
	human_readable_report = false   
	scheduler = main_scheduler 
} 

logger_t phantom_logger = logger_file_t {
        filename = "$phantom_log"
        level = info
        scheduler = main_scheduler
}

logger = phantom_logger

stat = {
    clear = true
    period = 1s
    time_format = full
    list = { benchmark_io }
    filename = "$stat_log"
}
