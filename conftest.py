"""pytest'in depo kokunu sys.path'e eklemesi icin bulunuyor.

Bu dosya sayesinde tests/ altindaki testler `core` ve `apps` paketlerini
import edebiliyor.
"""

import pytest


@pytest.fixture(autouse=True)
def _varsayilan_arayuz_dili():
    """Her test varsayilan arayuz diliyle baslar ve bitince ona doner.

    Gecerli dil modul duzeyinde tutuluyor: dili degistirip geri almayan bir
    test, sonraki testlerin metin karsilastirmalarini sirasina gore bozardi.
    """
    from apps.proxychat.i18n import DEFAULT_LANGUAGE, set_language

    set_language(DEFAULT_LANGUAGE)
    yield
    set_language(DEFAULT_LANGUAGE)


class SabitSesCihazlari:
    """Gercek ses donanimi yerine sabit bir liste.

    Pencere acilisinda mikrofon ve hoparlor listesini isletim sisteminden
    istiyor. Testler gercek donanima baksaydi sonuclari makineye gore
    degisirdi (bu makinede 7 giris, CI'da belki hic) ve her pencere testi
    QtMultimedia yuklerdi. `degistir` bir testin kulaklik takip cikarmasini
    taklit etmesini sagliyor.
    """

    def __init__(self):
        self.girisler = [(b"mic-ic", "Dahili mikrofon"), (b"mic-kulaklik", "Kulaklik mikrofonu")]
        self.cikislar = [(b"spk-ic", "Dahili hoparlor"), (b"spk-kulaklik", "Kulaklik")]
        self._dinleyiciler = []
        #: Listenin kac kez okundugu: acilista OKUNMAMASI testle kilitli.
        self.okuma = 0

    def list(self):
        self.okuma += 1
        return list(self.girisler), list(self.cikislar)

    @property
    def dinleyici_sayisi(self):
        return len(self._dinleyiciler)

    def watch(self, parent, callback):
        self._dinleyiciler.append(callback)

    def degistir(self, girisler=None, cikislar=None):
        """Kulaklik takildi/cikarildi: listeyi degistir ve dinleyicilere haber ver."""
        if girisler is not None:
            self.girisler = girisler
        if cikislar is not None:
            self.cikislar = cikislar
        for callback in list(self._dinleyiciler):
            callback()


@pytest.fixture(autouse=True)
def ses_cihazlari(monkeypatch):
    """Her test sabit bir ses cihazi listesiyle calisir; gerekirse degistirebilir."""
    from apps.proxychat import voice

    sahte = SabitSesCihazlari()
    monkeypatch.setattr(voice, "audio_devices", sahte)
    return sahte
