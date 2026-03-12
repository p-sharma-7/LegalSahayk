import time
import gc
from llama_cpp import Llama
from codecarbon import EmissionsTracker

def run_benchmark(device_name, gpu_layers):
    print(f"\n{'='*40}")
    print(f"Starting Benchmark: {device_name.upper()}")
    print(f"{'='*40}")
    
    # Initialize the carbon tracker
    tracker = EmissionsTracker(project_name=f"llama_{device_name}")
    tracker.start()
    
    # Start the timer
    start_time = time.time()
    
    print(f"Loading model on {device_name}...")
    llm = Llama(
        model_path="LegalSahyak_q4_k_m.gguf",
        n_gpu_layers=gpu_layers,
        n_ctx=8192,
        verbose=False 
    )

    system_message = "You are a corporate lawyer and you have " \
    "explain in simple words. Provide accurate, clear, and helpful answers."
    user_prompt = "Can you briefly explain what a non-disclosure agreement (NDA) is?"

    print("Generating response...")
    response = llm.create_chat_completion(
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_prompt}
        ],
        max_tokens=512,
        temperature=0.3,
        top_p=0.95
    )

    # Stop the timer and tracker
    end_time = time.time()
    emissions = tracker.stop()
    
    # Calculate metrics
    total_time = end_time - start_time
    output_text = response['choices'][0]['message']['content']
    tokens_generated = response['usage']['completion_tokens']
    tokens_per_second = tokens_generated / total_time
    
    print("\n--- Benchmark Results ---")
    print(f"Device: {device_name}")
    print(f"Total Time: {total_time:.2f} seconds")
    print(f"Generation Speed: {tokens_per_second:.2f} tokens/sec")
    print(f"Carbon Emissions: {emissions:.7f} kg CO2eq")
    print("-------------------------\n")
    
    # Clear memory to prevent crashes before the next run
    del llm
    gc.collect()
    
    return total_time, emissions, tokens_per_second

# --- Execute the Comparisons ---

# Run on CPU only
cpu_time, cpu_emissions, cpu_speed = run_benchmark(device_name="CPU", gpu_layers=0)

# Run on GPU (using -1 to offload everything)
gpu_time, gpu_emissions, gpu_speed = run_benchmark(device_name="GPU", gpu_layers=-1)

# --- Final Report ---
print("\n" + "#"*40)
print(" FINAL COMPARISON REPORT")
print("#"*40)
print(f"Time Difference:    GPU was {cpu_time - gpu_time:.2f} seconds faster.")
print(f"Speed Difference:   GPU generated {gpu_speed - cpu_speed:.2f} more tokens per second.")
print(f"Carbon Difference:  GPU emitted {abs(cpu_emissions - gpu_emissions):.7f} kg CO2eq {'more' if gpu_emissions > cpu_emissions else 'less'} than CPU.")