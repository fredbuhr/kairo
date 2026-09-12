model_list:
  - model_name: smart
    litellm_params:
      model: os.environ/OPENAI_MODEL
      api_key: os.environ/OPENAI_API_KEY
  - model_name: alternative
    litellm_params:
      model: os.environ/ANTHROPIC_MODEL
      api_key: os.environ/ANTHROPIC_API_KEY
  - model_name: local-fast
    litellm_params:
      model: os.environ/OLLAMA_MODEL
      api_base: http://ollama:11434
    model_info:
      input_cost_per_token: 0
      output_cost_per_token: 0

router_settings:
  routing_strategy: least-busy
  num_retries: 0
  timeout: 120

litellm_settings:
  num_retries: 0
  # Observability only. Nevolium Core remains the authority for policy, audit and spend accounting.
  # The OTEL exporter consumes correlation metadata already attached by Nevolium's model gateway.
  callbacks: ["langfuse_otel"]

general_settings:
  master_key: os.environ/LITELLM_MASTER_KEY
  database_url: os.environ/DATABASE_URL
