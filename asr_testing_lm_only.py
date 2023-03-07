# -*- coding: utf-8 -*-
"""asr_testing_lm_only

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1e5bKAc044g_okO8KTl8GNnv5cKQnkHQ9

# New Section
"""


# !pip install https://github.com/kpu/kenlm/archive/master.zip

# !pip install pyctcdecode==0.3.0
# !pip install datasets==2.10.0
# !pip install transformers==4.23.1
# !pip install jiwer

"""Let's load a small excerpt of the [Librispeech dataset](https://huggingface.co/datasets/librispeech_asr) to demonstrate Wav2Vec2's speech transcription capabilities.

We can see that the `logits` correspond to a sequence of 624 vectors each having 32 entries. Each of the 32 entries thereby stands for the logit probability of one of the 32 possible output characters of the model:
"""


from datasets import load_dataset, DatasetDict, Dataset, Audio
from huggingface_hub import Repository
from transformers import Wav2Vec2ProcessorWithLM, Wav2Vec2Processor, Wav2Vec2ForCTC
import torch

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
from tqdm import tqdm
from evaluate import load


target_lang="en"  # change to your target lang
speaker = "F01"
model_name = "yip-i/torgo_xlsr_finetune-" + speaker + "-2"

"""Cloning and uploading of modeling files can be done conveniently with the `huggingface_hub`'s `Repository` class. 

More information on how to use the `huggingface_hub` to upload any files, please take a look at the [official docs](https://huggingface.co/docs/hub/how-to-upstream).
"""


repo = Repository(local_dir="model_staging", clone_from=model_name)

"""Having cloned `xls-r-300m-sv`, let's save the new processor with LM into it.

As can be seen the *5-gram* LM is quite large - it amounts to more than 4 GB.
To reduce the size of the *n-gram* and make loading faster, `kenLM` allows converting `.arpa` files to binary ones using the `build_binary` executable.

Let's make use of it here.

## **1.Evaluation**
"""



"""### Processing Data"""


data = load_dataset('csv', data_files='output.csv')
data = data.cast_column("audio", Audio(sampling_rate=16_000))
timit = data['train'].filter(lambda x: x == speaker, input_columns=['speaker_id'])


processor = Wav2Vec2ProcessorWithLM.from_pretrained("model_staging")
model = Wav2Vec2ForCTC.from_pretrained(model_name)

import re
chars_to_ignore_regex = '[\,\?\.\!\-\;\:\"]'

def remove_special_characters(batch):
    batch["text"] = re.sub(chars_to_ignore_regex, '', batch["text"]).lower() + " "
    return batch

timit = timit.map(remove_special_characters)

def prepare_dataset(batch):
    audio = batch["audio"]

    # batched output is "un-batched" to ensure mapping is correct
    batch["input_values"] = processor(audio["array"], sampling_rate=audio["sampling_rate"]).input_values[0]
    batch["input_length"] = len(batch["input_values"])
    
    with processor.as_target_processor():
        # batch["labels"] = processor(batch["text"]).input_ids
        batch["labels"] = batch["text"]
        # print(processor(batch["text"]))
    return batch

timit = timit.map(prepare_dataset, remove_columns=timit.column_names, num_proc=4)
timit = timit.filter(lambda x: x < 25 * processor.feature_extractor.sampling_rate, input_columns=["input_length"])

timit[0]


def get_result(torgo_dataset):
  pred_str = []
  actual = []
  for i in range(torgo_dataset.num_rows):
    inputs = processor(torgo_dataset[i]["input_values"], sampling_rate=16_000, return_tensors="pt")
    with torch.no_grad():
      logits = model(**inputs).logits
    transcription = processor.batch_decode(logits.numpy()).text
    pred_str.append(transcription[0].lower())
    actual = processor.decode(torgo_dataset[i]["labels"]).text

  return pred_str, actual

# inputs = processor(timit[0]["input_values"], sampling_rate=16_000, return_tensors="pt")

# with torch.no_grad():

#   inputs = torch.tensor(timit[0]["input_values"], device="cpu").unsqueeze(0)
#   logits = model(inputs).logits

# pred_ids = torch.argmax(logits, dim=-1)
# pred_str = processor.batch_decode(pred_ids)[0]


def map_to_result(batch):
  with torch.no_grad():
    input_values = torch.tensor(batch["input_values"], device="cpu").unsqueeze(0)
    logits = model(input_values).logits

  pred_ids = torch.argmax(logits, dim=-1)
  batch["pred_str"] = processor.batch_decode(pred_ids)[0]
  batch["text"] = batch["labels"]
  
  return batch

# with torch.no_grad():
#   logits = model(**inputs).logits

# logits.shape

# transcription = processor.batch_decode(logits.numpy()).text
# transcription[0].lower()

# results = timit.map(map_to_result, remove_columns``=timit.column_names, batch_size=1, writer_batch_size=1, load_from_cache_file=False)
# pred_str, actual = get_result(timit)


pred_str = []
actual = []
for i in tqdm(range(timit.num_rows)):
  inputs = processor(timit[i]["input_values"], sampling_rate=16_000, return_tensors="pt")
  with torch.no_grad():
    logits = model(**inputs).logits
  transcription = processor.batch_decode(logits.numpy()).text
  pred_str.append(transcription[0].lower())

  actual.append(timit[i]["labels"])

wer_metric = load("wer")
wer = wer_metric.compute(predictions = pred_str, references = actual)
print("WER LOCATION")
print(wer)

# print("Test WER: {:.3f}".format(wer_metric.compute(pred_str, actual))