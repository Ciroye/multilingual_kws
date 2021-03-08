#%%
import numpy as np
import os
import glob
import pandas as pd
import matplotlib.pyplot as plt
import subprocess
import seaborn as sns
# import nltk
from typing import Set, List, Dict
import functools
from collections import Counter, OrderedDict
import csv
import pathlib
# import stopwordsiso as stopwords
import textgrid
import sox
from pathlib import Path
import pickle

import word_extraction

sns.set()
sns.set_palette("bright")
# sns.set(font_scale=1)

#%%
# how large is each language?
langs = {}
alignments = Path("/home/mark/tinyspeech_harvard/common-voice-forced-alignments")
for lang in os.listdir(alignments):
    if not os.path.isdir(alignments/lang):
        continue
    validated = alignments/lang/"validated.csv"
    if not os.path.isfile(validated):
        continue
    with open(validated, 'r') as fh:
        langs[lang] = len(fh.readlines())
langs = OrderedDict(sorted(langs.items(), key=lambda kv: kv[1], reverse=True))
# too many results in english
del langs["en"]

fig, ax = plt.subplots()
ax.bar(langs.keys(), langs.values())
ax.set_xticklabels(langs.keys(), rotation=90)
fig.set_size_inches(20,5)

# %%
LANG_ISOCODE="es"

if not os.path.isdir(f"/home/mark/tinyspeech_harvard/frequent_words/{LANG_ISOCODE}"):
    raise ValueError("need to create dir")
if not os.path.isdir(f"/home/mark/tinyspeech_harvard/frequent_words/{LANG_ISOCODE}/timings"):
    raise ValueError("need to create dir")

# %%
# generate most frequent words and their counts
alignments = Path("/home/mark/tinyspeech_harvard/common-voice-forced-alignments")
counts = word_extraction.wordcounts(alignments / LANG_ISOCODE / "validated.csv")

# %%
# look for stopwords that are too short
counts.most_common(20)

# %%
N_WORDS_TO_SAMPLE = 250
# get rid of words that are too short
SKIP_FIRST_N = 19 
to_expunge = counts.most_common(SKIP_FIRST_N)
non_stopwords = counts.copy()
for k,_ in to_expunge:
    del non_stopwords[k]
longer_words = [kv for kv in non_stopwords.most_common() if len(kv[0]) > 2]

print("counts for last word", longer_words[N_WORDS_TO_SAMPLE - 1])

# %%
# visualize frequencies of top words
fig,ax = plt.subplots()
topn = longer_words[:N_WORDS_TO_SAMPLE]
ax.bar([c[0] for c in topn], [c[1] for c in topn]);
ax.set_xticklabels([c[0] for c in topn], rotation=70);
ax.set_ylim([0,3000])
fig.set_size_inches(40,10)

# %%
# fetch timings for all words of interest
words = set([w[0] for w in longer_words[:N_WORDS_TO_SAMPLE]])
tgs = word_extraction.generate_filemap(lang_isocode=LANG_ISOCODE, alignment_basedir=alignments)
print("extracting timings")
timings, notfound = word_extraction.generate_wordtimings(words_to_search_for=words, mp3_to_textgrid=tgs, lang_isocode=LANG_ISOCODE, alignment_basedir=alignments)
print("errors", len(notfound))

# %%
# with open(f"/home/mark/tinyspeech_harvard/frequent_words/{LANG_ISOCODE}/all_timings.pkl", "wb") as fh:
#   pickle.dump(timings, fh)
#with open(f"/home/mark/tinyspeech_harvard/frequent_words/{LANG_ISOCODE}/all_timings.pkl", "rb") as fh:
#    timings = pickle.load(fh)

# %%
# write timings to csvs per word
MAX_NUM_UTTERANCES_TO_SAMPLE = 2500
df_dest = pathlib.Path(f"/home/mark/tinyspeech_harvard/frequent_words/{LANG_ISOCODE}/timings")
for word, times in timings.items():
    df = pd.DataFrame(times, columns=["mp3_filename", "start_time_s", "end_time_s"])
    if df.shape[0] > MAX_NUM_UTTERANCES_TO_SAMPLE:
        print(word, "SUBSAMPLING")
        df = df.sample(n=MAX_NUM_UTTERANCES_TO_SAMPLE, replace=False)
    print(df_dest / (word + ".csv"))
    df.to_csv(df_dest / (word + ".csv"), quoting=csv.QUOTE_MINIMAL, index=False)

# %%
# select commands and other words
data_dir = Path(f"/home/mark/tinyspeech_harvard/frequent_words/{LANG_ISOCODE}/clips/")
os.chdir(f"/home/mark/tinyspeech_harvard/train_{LANG_ISOCODE}_165/")

MIN_NUM_TRAIN_VAL=765
commands = []

words = os.listdir(data_dir)
for w in words:
    utterances = os.listdir(data_dir / w)
    if len(utterances) > MIN_NUM_TRAIN_VAL:
        commands.append(w)

other_words = set(words).difference(set(commands))

print("num commands", len(commands))
print("num other words", len(other_words))

# %%
# with open("commands.txt", 'w') as fh:
#     for w in commands:
#         fh.write(f"{w}\n")
# with open("other_words.txt", 'w') as fh:
#     for w in other_words:
#         fh.write(f"{w}\n")

# %%
with open("commands.txt", "r") as fh:
    commands = fh.read().splitlines()
with open("other_words.txt", "r") as fh:
    other_words = fh.read().splitlines()  

# %%
print(len(commands), len(other_words), len(set(commands).intersection(other_words)))

# %%
train_val_test_data = {}

VALIDATION_FRAC = 0.1
TEST_FRAC = 0.1

for c in commands:
    utterances = glob.glob(str(data_dir / c / "*.wav"))
    np.random.shuffle(utterances)
    
    n_val = int(VALIDATION_FRAC * len(utterances))
    n_test = int(TEST_FRAC * len(utterances))

    val_utterances = utterances[:n_val]
    test_utterances = utterances[n_val:n_val+n_test]
    train_utterances = utterances[n_val+n_test:]
    
    print(len(val_utterances), len(test_utterances), len(train_utterances))
    train_val_test_data[c] = dict(train=train_utterances, val=val_utterances, test=test_utterances)


# %%
# with open("train_val_test_data.pkl", 'wb') as fh:
#     pickle.dump(train_val_test_data, fh)

# %%

with open("train_val_test_data.pkl", 'rb') as fh:
    train_val_test_data = pickle.load(fh)

# %%
train_val_test_counts = [(w, len(d["train"]), len(d["val"]), len(d["test"])) for w,d in train_val_test_data.items()]
train_val_test_counts = sorted(train_val_test_counts, key=lambda c: c[1], reverse=True)
train_val_test_counts[:3]

# %%
fig,ax = plt.subplots()
btrain = ax.bar([c[0] for c in train_val_test_counts], [c[1] for c in train_val_test_counts])
bval   = ax.bar([c[0] for c in train_val_test_counts], [c[2] for c in train_val_test_counts], bottom=[c[1] for c in train_val_test_counts])
btest  = ax.bar([c[0] for c in train_val_test_counts], [c[3] for c in train_val_test_counts], bottom=[c[1]+c[2] for c in train_val_test_counts])
ax.set_xticklabels([c[0] for c in train_val_test_counts], rotation=70);
plt.legend((btrain[0], bval[0], btest[0]), ('train', 'val', 'test'))
fig.set_size_inches(40,20)

# %%
train_files = []
val_files = []
test_files = []
for w, d in train_val_test_data.items():
    train_files.extend(d["train"])
    val_files.extend(d["val"])
    test_files.extend(d["test"])
np.random.shuffle(train_files)

# %%
# for fname, data in zip(["train_files.txt", "val_files.txt", "test_files.txt"], [train_files, val_files, test_files]):
#    print(fname)
#    with open(fname, 'w') as fh:
#        for utterance_path in data:
#            fh.write(f"{utterance_path}\n")

# %%
with open("train_files.txt", 'r') as fh:
    train_files = fh.read().splitlines()
with open("val_files.txt", 'r') as fh:
    val_files = fh.read().splitlines()
with open("test_files.txt", 'r') as fh:
    test_files = fh.read().splitlines() 
print(len(train_files), train_files[0])
print(len(val_files), val_files[0])
print(len(test_files), test_files[0])
assert set(train_files).intersection(set(val_files)) == set(), "error: overlap between train and val data"
assert set(train_files).intersection(set(test_files)) == set(), "error: overlap between train and test data"           

# %%
# copy background data