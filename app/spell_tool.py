from symspellpy import SymSpell
import hgtk
import pandas as pd


def to_jamos(text):
    return hgtk.text.decompose(text)


sym_spell = SymSpell()
dictionary_path = "upload/ko_50k.txt"
sym_spell.load_dictionary(dictionary_path, 0, 1)

vocab = pd.read_csv("upload/ko_50k.txt", sep=" ", names=["term", "count"])
vocab.term = vocab.term.map(to_jamos)
vocab.to_csv("upload/ko_50k_decomposed.txt", sep=" ", header=None, index=None)
vocab.head()
