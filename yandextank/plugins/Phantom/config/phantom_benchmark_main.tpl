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
	
	    ${source_log_prefix}source_t source_log = ${source_log_prefix}source_log_t {
			filename = "$stpd"     
	    }
	
	    $ssl_transport
	    
		$comment_proto proto_t http_proto0 = proto_http_t { 
			$reply_limits
		$comment_proto }
		
	    $comment_proto proto_t none_proto = proto_none_t { }
	    
	    $proto
	    
	    $method_options
	    
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
	#human_readable_report = false
	scheduler = main_scheduler 
} 
