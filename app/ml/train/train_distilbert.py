import torch
from transformers import (
    DistilBertTokenizer, 
    DistilBertForSequenceClassification,
    TrainingArguments,
    Trainer
)
from datasets import load_dataset
import numpy as np
from sklearn.metrics import accuracy_score, precision_recall_fscore_support

# 1. Cargar datos
dataset = load_dataset('json', data_files={
    'train': 'data/train.jsonl',
    'validation': 'data/val.jsonl',
    'test': 'data/test.jsonl'
})

# 2. Tokenizer
tokenizer = DistilBertTokenizer.from_pretrained('distilbert-base-uncased')

def tokenize(batch):
    return tokenizer(batch['text'], truncation=True, padding=True, max_length=512)

dataset = dataset.map(tokenize, batched=True)

# 3. Modelo
model = DistilBertForSequenceClassification.from_pretrained(
    'distilbert-base-uncased',
    num_labels=5  # ham, spam, phishing, ai_generated, fraud
)

# 4. Training arguments
training_args = TrainingArguments(
    output_dir='./results',
    num_train_epochs=3,
    per_device_train_batch_size=16,
    per_device_eval_batch_size=32,
    warmup_steps=500,
    weight_decay=0.01,
    logging_dir='./logs',
    logging_steps=100,
    evaluation_strategy="steps",
    eval_steps=500,
    save_strategy="steps",
    save_steps=500,
    load_best_model_at_end=True,
    metric_for_best_model='f1',
    fp16=True  # Si tienes GPU
)

# 5. Métricas
def compute_metrics(pred):
    labels = pred.label_ids
    preds = pred.predictions.argmax(-1)
    precision, recall, f1, _ = precision_recall_fscore_support(
        labels, preds, average='weighted'
    )
    acc = accuracy_score(labels, preds)
    return {
        'accuracy': acc,
        'f1': f1,
        'precision': precision,
        'recall': recall
    }

# 6. Trainer
trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=dataset['train'],
    eval_dataset=dataset['validation'],
    compute_metrics=compute_metrics
)

# 7. Train
trainer.train()

# 8. Evaluate
results = trainer.evaluate(dataset['test'])
print(results)

# 9. Save
model.save_pretrained('ml/models/distilbert_spam_v1')
tokenizer.save_pretrained('ml/models/distilbert_spam_v1')
