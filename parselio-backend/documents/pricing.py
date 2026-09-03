# Price per 1,000 tokens, in USD. Check provider pricing pages before trusting these numbers.
MODEL_PRICING = {
    "groq/openai/gpt-oss-120b": {"input": 0.00015, "output": 0.00060},
    "gemini/gemini-3.6-flash":  {"input": 0.00010, "output": 0.00040},
}

def calculate_cost(model, input_tokens, output_tokens):
    prices = MODEL_PRICING[model]
    input_cost = (input_tokens / 1000) * prices["input"]
    output_cost = (output_tokens / 1000) * prices["output"]
    return round(input_cost + output_cost, 6)
