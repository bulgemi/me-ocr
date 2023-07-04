# _*_ coding: utf-8 _*_
from symspellpy import SymSpell, Verbosity
import hgtk


def to_jamos(text):
    return hgtk.text.decompose(text)


class TypoCorrection:
    def __init__(self):
        self.sym_spell = SymSpell(max_dictionary_edit_distance=2)
        self.sym_spell.load_dictionary("upload/ko_50k_decomposed.txt", 0, 1)

    def correction(self, text) -> str:
        best = {"spell": None, "count": 0}
        for suggestion in self.sym_spell.lookup(to_jamos(text), Verbosity.ALL):
            if suggestion.count > best['count']:
                best['spell'] = hgtk.text.compose(suggestion.term)
                best['count'] = suggestion.count
        return best['spell'] if best['spell'] is not None else text


if __name__ == "__main__":
    typo_cor = TypoCorrection()
    print(typo_cor.correction("안뇽하세요"))
    print(typo_cor.correction("비금여"))
    print(typo_cor.correction("검진뇨"))
    print(typo_cor.correction("금액산전내여"))
    print(typo_cor.correction("진료비총애"))
