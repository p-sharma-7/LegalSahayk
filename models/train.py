import torch
from unsloth import FastLanguageModel
from datasets import load_dataset
from trl import SFTTrainer, SFTConfig
# from transformers import TrainingArguments
from huggingface_hub import login

login(token="## YOUR HUGGINGFACE TOKEN HERE ##")
# ==========================================
# 1. HARDWARE MAXIMIZATION CONFIGURATION
# ==========================================
# Utilizing the 50 GB VRAM to the absolute limit.
max_seq_length = 8192 # Massive context window for 100-page RAG document chunks
dtype = torch.bfloat16 # Full 16-bit precision for exact legal vocabulary (no 4-bit shortcuts)
load_in_4bit = False # We have 50GB VRAM, so we train the base weights in high fidelity

print("Loading Llama 3.1 8B Instruct Base Model...")
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name = "unsloth/Meta-Llama-3.1-8B-Instruct",
    max_seq_length = max_seq_length,
    dtype = dtype,
    load_in_4bit = load_in_4bit,
)

# Attach a Massive LoRA Adapter
model = FastLanguageModel.get_peft_model(
    model,
    r = 128, # High rank (128) captures deep logical reasoning, not just syntax
    target_modules = ["q_proj", "k_proj", "v_proj", "o_proj",
                      "gate_proj", "up_proj", "down_proj"],
    lora_alpha = 128,
    lora_dropout = 0, 
    bias = "none",    
    use_gradient_checkpointing = "unsloth", 
    random_state = 3407,
)

EOS_TOKEN = tokenizer.eos_token

# ==========================================
# 2. DATASET PREPARATION
# ==========================================
print("Downloading and Formatting Datasets...")

# ==========================================
# 2. DATASET PREPARATION (CORRECTED SCHEMAS)
# ==========================================
print("Downloading and Formatting Datasets...")

# ------------------------------------------
# Dataset A: Knowledge Injection (Prarabdha)
# Schema: 'context', 'question', 'response'
# ------------------------------------------
def format_knowledge(examples):
    texts = []
    # Zip the exact column names from the Prarabdha dataset
    for ctx, q, r in zip(examples["context"], examples["question"], examples["response"]):
        
        # Handle potential None/null values gracefully
        ctx_text = f"### Legal Context:\n{ctx}\n\n" if ctx else ""
        q_text = f"### Question:\n{q}\n\n" if q else ""
        r_text = f"### Legal Reasoning:\n{r}" if r else ""
        
        text = f"{ctx_text}{q_text}{r_text}{EOS_TOKEN}"
        texts.append(text)
    return { "text" : texts }

dataset_a = load_dataset("Prarabdha/indian-legal-supervised-fine-tuning-data", split="train")
dataset_a = dataset_a.shuffle(seed=3407).select(range(50000))
dataset_a = dataset_a.map(format_knowledge, batched = True)


# ------------------------------------------
# Dataset B: Behavioral Alignment (Aalap)
# Schema: 'system_prompt', 'user_prompt', 'input_text', 'output_text'
# ------------------------------------------
def format_behavior(examples):
    texts = []
    # Zip the exact column names from the Aalap dataset
    for sys, usr, inp, out in zip(examples["system_prompt"], examples["user_prompt"], examples["input_text"], examples["output_text"]):
        
        # We must check for None values because the dataset contains nulls
        sys_text = f"### System:\n{sys}\n\n" if sys else ""
        usr_text = f"### Instruction:\n{usr}\n\n" if usr else ""
        inp_text = f"### Input:\n{inp}\n\n" if inp else ""
        out_text = f"### Response:\n{out}" if out else ""
        
        text = f"{sys_text}{usr_text}{inp_text}{out_text}{EOS_TOKEN}"
        texts.append(text)
    return { "text" : texts }

dataset_b = load_dataset("opennyaiorg/aalap_instruction_dataset", split="train")
dataset_b = dataset_b.map(format_behavior, batched = True)

# ==========================================
# 3. PHASE A: KNOWLEDGE INJECTION TRAINING
# ==========================================
# ==========================================
# 3. PHASE A: KNOWLEDGE INJECTION TRAINING
# ==========================================
print("Starting Phase A: Deep Knowledge Injection...")
trainer_a = SFTTrainer(
    model = model,
    processing_class = tokenizer, # FIXED: Replaced 'tokenizer'
    train_dataset = dataset_a,
    # SFTConfig replaces TrainingArguments in the newer API
    args = SFTConfig(
        dataset_text_field = "text", # MOVED inside config
        max_length = max_seq_length, # FIXED: Renamed from max_seq_length
        dataset_num_proc = 4,        # MOVED inside config
        per_device_train_batch_size = 4,
        gradient_accumulation_steps = 4, 
        num_train_epochs = 1, 
        warmup_steps = 300,          # FIXED: Replaces deprecated warmup_ratio
        learning_rate = 2e-4,
        lr_scheduler_type = "cosine", 
        bf16 = True,
        logging_steps = 50,
        optim = "adamw_8bit",
        output_dir = "legalsahyak_checkpoints_phase_a",
        save_strategy="no",
    ),
)
trainer_a.train()
# ==========================================
# 4. PHASE B: BEHAVIORAL ALIGNMENT (WITH NEFTUNE)
# ==========================================
print("Starting Phase B: Behavioral Alignment...")
trainer_b = SFTTrainer(
    model = model,
    processing_class = tokenizer, # FIXED: Replaced 'tokenizer'
    train_dataset = dataset_b,
    args = SFTConfig(
        dataset_text_field = "text", 
        max_length = max_seq_length, 
        dataset_num_proc = 4,
        per_device_train_batch_size = 4,
        gradient_accumulation_steps = 4,
        num_train_epochs = 1, 
        warmup_steps = 130, # ~10% of the Aalap dataset steps
        learning_rate = 5e-5, 
        lr_scheduler_type = "cosine",
        bf16 = True,
        logging_steps = 50,
        optim = "adamw_8bit",
        output_dir = "legalsahyak_checkpoints_phase_b",
        neftune_noise_alpha = 5, 
        save_strategy="no",
    ),
)
trainer_b.train()

# ==========================================
# 5. THE COMPRESSOR (GGUF CPU EXPORT)
# ==========================================
print("Training Complete! Merging LoRA and Quantizing to CPU-friendly GGUF...")

export_directory = "LegalSahyak_GGUF_Model"

# Unsloth automatically handles the downloading of llama.cpp, fusing the weights, 
# and compressing the 16GB model down to ~5GB.
# q4_k_m is the mathematical sweet spot for CPU offline inference.
model.save_pretrained_gguf(
    export_directory, 
    tokenizer, 
    quantization_method = "q4_k_m"
)

print(f"Success! The fully offline, CPU-ready model is saved in the '{export_directory}' folder.")
print("You can now download the '.gguf' file to your local PC.")