# Not — Guitar Pro 8 kara kutu incelemesi: dosya biçimi, ses senkronu, tel kuralı

> **Durum (24 Ekim 2026):** Bölüm 1–3 ölçüm ve analiz. **Bölüm 4.1 uygulandı:** MusicXML artık tek part ve iki
> portre olarak yazılıyor; yazıcı, okuyucu ve görüntüleyici buna göre değişti (aşağıda "Uygulama 4.1").
> **4.2 (`.gp` yazıcı) YARIM** (nota, enstrüman ve senkron çalışıyor; gömülü ses Guitar Pro'da yüklenmiyor).
> **Ek A:** "tel merkezi" deneyi (kural sağlanmadı). **Ek B:** devlog'a girmemiş önceki ölçümler.
> **Ürün doğruluğu bu notta DEĞİŞMEDİ:** model `tabcrnn_deep2.pt` + `tabcrnn_deep2.cal.json`, gaps_test nota F1
> 0.818. Hiçbir değişiklik commit edilmedi (kullanıcı kararı, 26 Ekim). Dal `Armagan-katman-6`. Kod `scripts/eval/gp/` altında, sonuçlar
> `docs/results/gp/` altında, testler `tests/test_gp_rule.py` ve `tests/test_gaps_score.py`. Guitar Pro 8.1.5
> (build 31), 7 günlük resmi deneme sürümü.

## Soru
Piyasanın standart tab yazılımı Guitar Pro nasıl çalışıyor ve bizim projeye ne aktarılabilir? Dört alt soru:
1. Dosyaları nasıl saklıyor?
2. Bizim MusicXML çıktımızı doğru okuyor mu?
3. Tel bilgisi verilmeyen notalara hangi teli seçiyor?
4. Bir ses kaydını notayla nasıl senkronize ediyor?

## Yasal sınır: ne yapıldı, ne yapılmadı
- **Lisans (EULA, Fransız hukuku, madde 4):** Programın değiştirilmesini, decompile edilmesini (kodunun açılıp
  okunmasını), bütünüyle ya da kısmen çoğaltılmasını yasaklıyor.
- **Bu yüzden yalnızca kara kutu yöntemi kullanıldı.** Programa kendi hazırladığımız girdileri verdik ve
  ürettiği çıktıları inceledik.
- **Yapılmayanlar:**
  - EXE ve DLL'ler açılmadı ve disassemble edilmedi.
  - Deneme süresi ve lisans aşılmadı.
  - Ses bankaları (`.gp7bank`) okunmadı ve kopyalanmadı.
  - Guitar Pro'nun sesleri eğitimde kullanılmadı.
- **İncelenenler:**
  - Kurulumdaki dosya adları.
  - Açık JSON tanım dosyaları.
  - Programın kaydettiği bizim içeriğimizi taşıyan `.gp` dosyaları.
  - Resmî kullanım kılavuzu.
- **Dosya biçimi bilgisi yeni değil:** `.gp` biçimi açık kaynak alphaTab, PyGuitarPro ve benzeri projelerde zaten
  belgelenmiş; birlikte çalışabilirlik bilgisi sayılır.

## Kurulum (nasıl yapıldı)
1. **winget denemesi:** `winget install ArobasMusic.GuitarPro.8` → **404**. Paketteki indirme adresi eskimiş.
2. **Resmî site:** `guitar-pro.com/download-guitar-pro` formu bir e-posta ve onay istiyor. Kullanıcının izniyle
   doldurulup "Download manually" seçildi. Sonuç: `download.assets-arobas-music.com/GP_8/8.1.5.31/` adresinden
   imzalı ve süreli (24 saat geçerli) bir indirme bağlantısı.
3. **Kurulum dosyası:** `guitar-pro-soundbank-full.exe`, 1,04 GB, Inno Setup.
   - **Authenticode imzası geçerli:** SARL AROBAS MUSIC, Lille, FR.
   - Sessiz kurulum: `/SILENT /TASKS="desktopicon"`.
   - Kısayol: `C:\Users\Public\Desktop\Guitar Pro 8.lnk`.

## 1. Envanter (yalnızca dosya adları; kod okunmadı)
| Yer | İçerik | Ne anlıyoruz |
|---|---|---|
| `C:\Program Files\Arobas Music\Guitar Pro 8\` | `GuitarPro.exe` 50 MB, `GPCore.dll` 10,6 MB, `GPIO.dll` 6,5 MB, Qt5 | Qt5 / C++ masaüstü uygulaması. Çekirdek, dosya G/Ç ve arayüz ayrı modüllerde |
| ses modülleri | `GPRSE.dll`, `AMAudio`, `AMSoundFont`, `AMPickupModeling`, `AMOverloud` | RSE (Realistic Sound Engine) örnek tabanlı çalıyor. Pikap ve amfi modellemesi ayrı |
| üçüncü parti | `rubberband.dll`, `samplerate.dll`, `FLAC`, `vorbis`, `libxml2`, `libxslt`, `Zip`, `sentry` | Rubber Band: sesi perdesini bozmadan yavaşlatma ("slow down"). libxml2/xslt: MusicXML ve GPIF. Sentry: çökme raporu |
| özel | `polytuner.dll`, `simbals.dll`, `FretlightApi.dll` | Polifonik akort aleti (belgede var). `simbals`: adı bir müzik analizi şirketine işaret ediyor, işlevi belgelenmemiş. **Kod açılmadığı için bilinmiyor** |
| `C:\ProgramData\Arobas Music\Soundbanks\…standard\` | 350 `.gp7bank` (923 MB) + 372 `.json` | Kapalı ses biçimi. JSON yalnızca tanım: id, ad, açıklama, `instrumentSet` (ör. `steelGuitar`) |
| `%APPDATA%\Arobas Music\guitarpro8\` | şablonlar, efekt zinciri ön ayarları | Kullanıcı ayarları |

**Guitar Pro sesten nota çıkarmıyor.** Resmî kılavuza ve kurulum dosyalarına göre ses kanalı yalnızca
eşlik ve dinleme amaçlı. Senkronizasyon elle yapılıyor. Bizim projenin yaptığı iş, yani otomatik ses → TAB,
Guitar Pro'da **yok**.

## 2. `.gp` dosya biçimi (kaydedilen dosyalardan)
- **Kapsayıcı:** `.gp` bir **zip** arşivi.
  - Asıl partisyon `Content/score.gpif` (XML).
  - Yanında görünüm ve sayfa ayarları: `BinaryStylesheet`, `ScoreViews/*.gpsv`, `Stylesheets/*.gpss`,
    `LayoutConfiguration`, `PartConfiguration`, `Preferences.json`.
  - Kökte `VERSION` (= `7.0`) ve `meta.json` (`hasAudio`).
- **Başlık bilgisi:** `GPVersion 8.1.5`, `GPRevision 13008` (gerekli 12024), `EncodingDescription GP8`.
- **İlişkisel tablolar:** `MasterBars → Bars → Voices → Beats → Notes`, ayrıca `Rhythms`.
  - Her katman alttakini **kimlik listesiyle** gösteriyor.
  - Örnek: `<Beats>0 0 0 0</Beats>`, `<Voices>0 -1 -1 -1</Voices>` (-1 = boş ses).
- **Önemli tuzak (çözümleyiciyi bozdu, düzeltildi):** Guitar Pro aynı içerikli Beat ve Note kayıtlarını **tek
  kimlikle** saklıyor ve tekrar kullanıyor.
  - Örnek 1: 8 tane E4 sekizlik tek Beat olarak saklanıyor.
  - Örnek 2: 524 notalık parçada Note tablosunda yalnızca 64 benzersiz kayıt var.
  - **Sonuç:** Notalar kimliğe göre değil, **sıradaki konuma** (slot) göre sayılmalı.
- **Nota alanları:** `Midi`, `String`, `Fret`, `ConcertPitch`, `TransposedPitch`.
  - İsteğe bağlı: `ShowStringNumber` (A3'te görüldü).
  - **`String 0` = en kalın tel**, gtab ile aynı.
- **Kanal alanları:** `InstrumentSet/Type` (ör. `acousticPiano`, `steelGuitar`), `Sounds/Sound/MIDI/Program`,
  `Staves/Staff/Properties`.
  - Staff özellikleri: `Tuning` (Pitches `40 45 50 55 59 64`), `CapoFret`, `FretCount`, `PartialCapoFret`,
    `PartialCapoStringFlags`, `ChordCollection`.

## 3. Testler
Test dosyaları `docs/results/gp/probe/` altında. Hepsi bizim içeriğimiz; Guitar Pro yalnızca "kaydet" işini yaptı.

| Test | Girdi | Guitar Pro'da ne yapıldı | Ne ölçer |
|---|---|---|---|
| A | gaps_test `019_Vpswc`, bizim pipeline (ses ve edisyon modu; BPM 80, 4/4 elle verildi) | MusicXML aç → `.gp` kaydet | Bizim MusicXML'imiz doğru okunuyor mu |
| B | `make_probe.py`: yalnızca perde bilgisi olan 22 ölçü (tek notalar, kromatik E2→E5, tiz melodi, C5↔E4 sıçraması, tekrarlanan E4, 5 akor) | aç → hiçbir şey değiştirmeden `.gp` kaydet | Tel bilgisi yokken hangi teli seçiyor |
| C | A'nın `.gp` dosyası + `019_Vpswc.wav` | Ses ekle, 3. ve 5. ölçüye senkronizasyon noktası koyup kaydır, kaydet | Ses ve senkron nasıl saklanıyor |
| A2 | A'nın **tek parça + 2 portre** hali + `instrument-sound` | aç → kaydet | Exporter düzeltmesi |
| A3 | A'nın **tek portre** hali; her notada tel ve perde | aç → kaydet | Alternatif düzen |

Çözümleme: `python -m scripts.eval.gp.gpif <dosya.gp>`.

### Sonuç A: bizim MusicXML'imiz
| Kontrol | Sonuç |
|---|---|
| TAB tel/perde (`<string>/<fret>`) | **524/524 birebir korunuyor** |
| Ölçü sayısı, ölçü imi, tempo | korunuyor (45 ölçü, 4/4, ♩ = 80) |
| Kanal | **Sorun:** "Gitar" ve "TAB" **iki ayrı kanal** oluyor. Guitar Pro her `<part>` için bir kanal açıyor |
| Enstrüman | **Sorun:** İki kanal da `acousticPiano` (Program 1). `midi-program 25` dikkate alınmıyor |
| Ritim | 32'lik ve 64'lük üçlemeler gibi çalınması güç değerler var (kuantalamamızdan). Ayrıca incelenmeli |

**Yan bulgu:** Nota portremizde tel bilgisi yok. Guitar Pro bu notaları kendi kuralıyla yerleştirince sonuç
**edisyon modumuzla %93 (488/524)**, **ses modumuzla %40 (207/524)** örtüştü.

### Sonuç A2 / A3: exporter düzeltmesi denemesi
| | A (şu anki) | **A2: tek parça, 2 portre** | A3: tek portre |
|---|---|---|---|
| Kanal | 2 | **1** | 1 |
| Nota + TAB birlikte | hayır | **evet** | hayır. TAB yok, teller notanın üstünde ③ ⑥ |
| Nota / ses sayısı | 524 / 1 | **524 / 1 (ikilenme yok)** | 524 / 1 |
| Bizim tel/perde | 524/524 (TAB kanalında) | **520/524** | 524/524 |
| Enstrüman | piyano | piyano | piyano |

- **A2'deki 4 uyuşmazlığın sebebi:** Hepsi akorda **aynı perdenin iki telde** çaldığı yerler (unison).
  - 24\. ölçüde iki B2: 6. tel 7. perde ve 5. tel 2. perde.
  - 34\. ölçüde iki C4.
  - Guitar Pro TAB notalarını nota portresindekilerle perdeye göre eşliyor, aynı perdeden iki nota olunca karışıyor.
  - Gerçek gitarda aynı anda unison nadir. Bunlar README22'deki hayalet kopya notalardan olabilir.
- **Enstrüman MusicXML ile düzeltilemedi.** `instrument-sound pluck.guitar.nylon-string`, part-name ve
  instrument-name denendi; Guitar Pro MusicXML'den gelen kanalı her durumda piyano açıyor.
- **Kesin çözüm `.gp` dosyasını doğrudan yazmak:** `InstrumentSet` ve `Sound` alanlarını biz doldururuz.

### Sonuç C: ses ve senkron nasıl saklanıyor
- **Ses dosyası:** wav, zip'e **olduğu gibi** gömülüyor (`Content/Assets/<id>.wav`, 30 MB → zip içinde 25 MB).
  - `<Assets>`: kaynak yol, sha1 kimliği, gömülü yol.
  - `<BackingTrack>`: kanal ayarları, `Semitones/Cents`, `FramePadding`.
- **Senkronizasyon noktaları:** `MasterTrack/Automations` içinde `Type = SyncPoint` olarak duruyor. Alanlar:

  | Alan | Anlam |
  |---|---|
  | `BarIndex` | hangi ölçünün başı (0'dan) |
  | `BarOccurrence` | tekrarlı ölçülerde kaçıncı geçiş |
  | `FrameOffset` | o ölçünün sesteki yeri, **örnek sayısı** |
  | `ModifiedTempo` | bu noktadan sonrakine kadar geçerli tempo |
  | `OriginalTempo` | notadaki tempo |

- **`FrameOffset` birimi:** Dosya 48 kHz olmasına rağmen **44 100 Hz** üzerinden sayılıyor. Formül:
  `ModifiedTempo = (ölçü sayısı × vuruş/ölçü) / (ΔFrameOffset / 44100) × 60`.

  | Aralık | Süre | Hesap | Dosyada |
  |---|---|---|---|
  | ölçü 0 → 2 | 282 000 / 44 100 = 6,395 sn | 8 / 6,395 × 60 = **75,064** | 75,06384 |
  | ölçü 2 → 4 | 265 000 / 44 100 = 6,009 sn | **79,879** | 79,878975 |

  48 kHz ile hesaplanınca 81,70 ve 86,94 çıkıyor, uymuyor.
- **Son nokta:** Son senkronizasyon noktası bir önceki tempoyu sürdürüyor.

### Sonuç B: tel kuralı
Guitar Pro'nun seçimleri (`python -m scripts.eval.gp.gpif docs/results/gp/probe/B_pitch_only.gp`):
- **Tek notalar ve kromatik dizi:** Hep **ilk pozisyon**. Her telde perde 0–4, sonra bir üst tele geçiyor.
  E4'ten sonra 1. telde 12. perdeye kadar **pozisyon değiştirmeden** tırmanıyor.
- **Tiz melodi A4–E5:** Tamamı 1. telde, perde 5–12.
- **C5 → E4 → C5 → E4 → E4…:**
  - İlk E4 **2. tel 5. perdede**: iki komşusu C5, 8. perde.
  - Sonraki E4 **açık telde**: arkasından E4'ler geliyor.
  - Yani **komşu notalara bakıyor**.
- **Akorlar standart şekillerde:**
  - C (x32010)
  - E (022100)
  - F barre (133211)
  - D (xx0232)
  - A3–E4–A4 → 5. pozisyonda sıkışık şekil

**Taklit (model):** `scripts/eval/gp/gp_rule.py::gp_like`.
- Her vuruştaki nota grubu (tek nota ya da akor) için aday yerleşimler: **farklı teller** ve basılan perdelerin
  açıklığı **≤ 4**.
- Maliyet fonksiyonu:
  - **durağan maliyet** = a × (basılan perdelerin toplamı)
  - **geçiş maliyeti** = b × |el kayması|; el = basılı perdelerin ortalaması, açık tel = 0
- Tüm parça boyunca en ucuz yol Viterbi ile bulunuyor.
- **Ağırlıkların türetilmesi:** C5–E4 testindeki iki davranışın ikisini birden üretmek için a < 2b ve b < 9a
  gerekiyor. Tarama sonucu:

  | b (a = 1) | 0,1–0,4 | **0,5–0,9** | 1,0 | 1,5 |
  |---|---|---|---|---|
  | Guitar Pro ile aynı | 86/87 | **87/87** | 86/87 | 85/87 |

  Seçim: **a = 1, b = 0,5**. Bu, Guitar Pro'nun gerçek algoritması değil. **Davranışını bu probda birebir
  üreten bir model** (87 nota, küçük örneklem). `tests/test_gp_rule.py` bu eşleşmeyi koruyor.

**Karşılaştırma** (`python -m scripts.eval.gp.gp_rule`, log `docs/results/gp/gp_rule.log`;
ses = `tabcrnn_deep2.pt`, edisyon = `edition_seq.pt`, eval_edition ile aynı veri ve eşleme):

1) Tel uyumu, gerçek notalar (partisyonda etiketli notalar):

| yöntem | gaps_val | gaps_test | GuitarSet val |
|---|---|---|---|
| naif (en düşük perde) | 0,702 | 0,745 | 0,206 |
| **Guitar Pro kuralı (taklit)** | 0,726 | 0,797 | 0,214 |
| **EDİSYON dizi modeli** | **0,766** | **0,815** | 0,425 |
| ses / greedy (duyulan konum) | 0,610 | 0,629 | **0,878** |

2) Guitar Pro kuralıyla aynı yere koyma oranı (tüm notalar):

| yöntem | gaps_val | gaps_test | GuitarSet val |
|---|---|---|---|
| naif | 0,948 | 0,933 | 0,987 |
| edisyon | 0,870 | 0,897 | 0,655 |
| ses | 0,581 | 0,573 | 0,231 |

3) Uçtan uca (gaps_test, deep2'nin bulduğu notalar, ±50 ms; etiketli 14 082, bulunan 11 447):

| yöntem | tel: bulunanlarda | tüm etiketlilerde |
|---|---|---|
| naif | 0,747 | 0,607 |
| Guitar Pro kuralı (taklit) | 0,777 | 0,632 |
| **EDİSYON** | **0,803** | **0,653** |
| ses | 0,621 | 0,505 |

**Yorum:**
- **Basılı klasik edisyona (GAPS) en yakın yöntem bizim edisyon modelimiz.** Guitar Pro kuralını gaps_val'de
  +4,0, gaps_test'te +1,8, uçtan uca +2,6 puan geçiyor.
  - Guitar Pro kuralı da naif kuraldan +2,4 / +5,2 puan iyi; aradaki farkı komşu bağlamı sağlıyor.
- **Gerçekte çalınan tele (GuitarSet, hex pikap) bütün kurallar kötü:** Guitar Pro kuralı 0,214, naif 0,206.
  Burada yalnızca **ses modu** işe yarıyor (0,878). Çelik telli GuitarSet çalıcıları yüksek pozisyonları çok
  kullanıyor; kural ise "alçak pozisyon" varsayıyor.
- **Bu, README22'deki hibrit mod kararını destekliyor:**
  - **Edisyon modu** = "bir editör nasıl yazardı". Endüstri standardı yazılımın varsayılanını geçiyor.
  - **Ses modu** = "çalıcı nerede çaldı". Kuralların hiçbirinin bilemeyeceği bilgiyi taşıyor.
  - İki mod karışmamalı.
- **Sunum için kullanılabilecek cümle:** "Edisyon modumuz, Guitar Pro 8'in tel atama davranışını taklit eden
  kuraldan GAPS test setinde 1,8 puan, uçtan uca 2,6 puan daha doğru."
  - **Uyarı:** Burada kıyaslanan Guitar Pro'nun kendisi değil, onu 87/87 taklit eden modelimiz.

## 4. Projeye aktarılabilecekler (öncelik sırasıyla; hiçbiri henüz uygulanmadı)
1. **MusicXML düzeni (küçük):** `gtab/render/musicxml.py` iki `<part>` yerine **tek part, `<staves>2</staves>`**
   yazsın (A2 düzeni).
   - Guitar Pro'da tek kanal, nota ve TAB birlikte görünür.
   - **Ön koşul:** MuseScore, alphaTab ve `gaps_score` gidiş-dönüş testinin de bu düzeni okuduğu ayrıca
     doğrulanmalı.
2. **Doğrudan `.gp` yazıcı (orta):** `score.gpif` + zip.
   - Doğru enstrüman (`InstrumentSet` gitar), akort, kapo.
   - **Kullanıcının kendi kaydı gömülü** (`Content/Assets`).
   - **Her ölçü başına senkronizasyon noktası:** BeatNet'in ölçü başlarından,
     `FrameOffset = round(t × 44100)`, `ModifiedTempo` yukarıdaki formülle.
   - Kullanıcı dosyayı açınca TAB kendi çalışını izleyerek akar; yavaşlatma ve döngü hazır gelir. Guitar Pro'da
     bu senkron elle, ölçü ölçü yapılıyor.
   - Biçim bilgisi için alphaTab'ın GP7 exporter'ı referans olabilir.
3. **Tel kuralı:** Ürüne kural eklemeye gerek yok, edisyon modu zaten daha iyi. `gp_like` yalnızca
   **karşılaştırma tabanı** olarak kalsın.
4. **Unison akor notaları:** Aynı anda iki telde aynı perde. Hayalet analizine (README22 Adım 5) bir kategori
   olarak eklenebilir.
5. **Ritim:** 32'lik ve 64'lük üçlemeler kuantalamada yasaklanabilir. Ayrı ölçüm gerekli.

## Uygulama 4.1: MusicXML tek part + iki portre (24 Ekim 2026)
| Dosya | Değişiklik |
|---|---|
| `gtab/render/musicxml.py` | Tek `P1` part. `<staves>2</staves>`; `clef number=1` G8vb, `clef number=2` TAB, `staff-details number=2` (akort, kapo). Her ölçüde önce staff 1 (voice 1, parmak), sonra `<backup>` ve staff 2 (voice 5, tel/perde). Notalara `<staff>` etiketi. `write_musicxml` 40 satır kuralı için `_tempo` ve `_staff_notes` olarak bölündü |
| `gtab/data/gaps_score.py` | `staves_of(part)`, `parse_part(part, staff)`. `score_notes` her partın her portresini ayrı akış olarak okuyor. Zaman (`pos`) tüm notalardan yürüyor, çünkü `<backup>` iki portrenin ortak saatini geri sarıyor |
| `scripts/eval/gv/test_c_sanity.py` | TAB notaları: tek partta `<staff>2`, eski iki partlı düzende P2 |
| `scripts/app/tab_viewer.html` | `mergeStaves`. alphaTab bir kanalın **tüm portrelerini çalıyor**, yani her nota iki kez duyuluyordu (509 notada 1018 NoteOn), ve tek bir portre susturulamıyor. Bu yüzden nota portresi tutuluyor; TAB portresinden tel/perde ve akort ona kopyalanıp TAB portresi atılıyor. Eşleme aynı ölçü + ölçü içi başlangıç + perde ile yapılıyor; ses indeksi kullanılamıyor çünkü alphaTab TAB notalarını `<voice>5` yüzünden 5. seste tutuyor |
| `tests/test_gaps_score.py` | `test_one_part_two_staves`: TAB notası bir kez sayılıyor, parmak taşınıyor, ölçü uzunluğu doğru |

**Neden önce TAB portresini tutmak çalışmadı:** İlk denemede nota portresi atılıp TAB portresi tutuldu. Sonuçta
8vb anahtarı kayboldu, notalar 5. ses olduğu için gri ("ikincil ses") çizildi, ve parmak eşleştirmesi 0/299 kaldı.
Parmak eşleştirmesinin iki sebebi vardı: ses indeksi farkı, ve parmağı olmayan notaların değeri `-1`
(`NoOrDead`), `-2` değil. Bu yüzden ters yöne çevrildi.

**Doğrulama:**

| Kontrol | Sonuç |
|---|---|
| Tüm unittest'ler | **238/238 geçti** (önce 237 + yeni test) |
| GAPS'te okuyucu davranışı | 300 dosyanın 604 partının **hiçbirinde `<staff>` yok**, okuyucu birebir eski yoldan çalışıyor |
| `eval_score` A (yaz → oku) | **202 partisyon, 159 796 nota, birebir 1.0000, ölçü doluluğu bozuk 0/14 398**; README16 ile aynı |
| alphaTab, yeni ses çıktısı (`019_Vpswc`) | 1 kanal; bilgi satırı 45 ölçü / **509 nota** / E2…E4 / 80 BPM; NoteOn **509** (birleştirmeden önce 1018) |
| alphaTab, yeni edisyon çıktısı | 524/524 notada tel; **299/299 parmak korundu**; perdeler değişmedi; 8vb anahtarı ve siyah notalar |
| alphaTab görünüm modları | Nota+TAB, yalnız TAB, yalnız nota: üçü de doğru |
| alphaTab, eski iki partlı dosya | Dokunulmuyor (2 kanal), eskisi gibi açılıyor |
| Guitar Pro (`A4_new_ses.musicxml`, kullanıcı ekranı) | **Tek kanal "1. Gitar"**, nota + TAB birlikte, 45 ölçü, ♩ = 80, akort EADGBE; TAB rakamları alphaTab ile aynı, A2'deki kırmızı rakamlar yok. Enstrüman hâlâ piyano ("Stringed: Off"); beklenen, 4.2'nin konusu |

**Eskiden kalan ve bu işle ilgisiz:** Parmak `0` olan notalar alphaTab'da "t" (başparmak) olarak gösteriliyor
(`Fingers.Thumb = 0`). Edisyon çıktısındaki 0'ın anlamı ayrıca kontrol edilmeli.

## Uygulama 4.2: doğrudan `.gp` yazıcı (24–26 Ekim 2026) — YARIM
**Kod (commitsiz):**
- `gtab/render/gpfile.py`: `write_gp(...)`, `bar_times`, `sync_points`, `audio_padding`, `fallback_position`.
- `scripts/app/transcribe.py`: `--out x.gp`, `--no-audio`.
- `scripts/app/tab_viewer.html`: `.gp` dosyasını da açıyor.
- `tests/test_gpfile.py`: 8 test (toplam 246 test geçiyor).

**Biçim bilgisi** (kullanıcının Guitar Pro'da kaydettiği referans dosya `D_reference.gp`'den; yalnız alan adları):

| Alan | Guitar Pro'da nasıl yazılıyor |
|---|---|
| Naylon gitar kanalı | `InstrumentSet Type nylonGuitar`, `Program 24`, ses `Concerto-Nylon` (`Stringed/Acoustic Guitars/Nylon Guitar`), `PlayingStyle StringedFinger`, `IconId 23`, kanal `RSE/ChannelStrip`, pikap + efekt zinciri |
| Oktav | Kanalda `Transpose Octave -1`; ölçüde yalnız `Clef G2` (`Ottavia 8vb` eklenince notalar bir oktav yüksek çiziliyordu) |
| Akort, kapo | `Tuning Pitches`, `CapoFret` |
| Perde numarası | **Kapodan sayılıyor**; MIDI = akort + kapo + perde (Drop D + kapo 2 ile doğrulandı) |
| Bağ | `Tie origin/destination` |
| Sol el parmağı | `LeftFingering` harfle: 1 = I, 2 = M, 3 = A, 4 = C; açık tel (0) yazılmaz |
| Ritim | `NoteValue`, `AugmentationDot`, `PrimaryTuplet 3:2`; vuruşta `Dynamic MF` (yoksa alphaTab "f" gösteriyor) |

**Doğrulama:**
- **alphaTab (Playwright):** Tek "Nylon Guitar" kanalı, 45 ölçü, 509 nota bir kez çalınıyor. Gömülü ses ve 45 senkron
  noktası tanınıyor. Edisyon dosyasında 299/299 parmak; MusicXML'deki "0 = t (başparmak)" sorunu .gp'de yok.
- **Guitar Pro (kullanıcı ekranı):**
  - Kanal adı, gitar ikonu, Stringed On ve nota + TAB doğru.
  - Ölçü başı senkron noktaları okunuyor: ses panelinde ▽ işaretleri ve 96.6 / 81.4 / 77.1 / 80.7 / 86.1 bpm.
- **Ölçü 0 kayıttan önce başlıyorsa** (019_Vpswc'de −0,79 sn):
  - Negatif `FrameOffset` ("raw") Guitar Pro tarafından kırpılıyor; 0. ölçü temposu 141.6'ya bozuluyor.
  - **`FramePadding` + kaydırılmış konumlar doğru** (96.6). "raw" seçeneği koddan çıkarıldı.
  - Guitar Pro tempoları konumlardan kendisi yeniden hesaplıyor.

**Açık sorun — gömülü ses yüklenmiyor:** Guitar Pro "Failed to locate audio file" diyor. Daraltma, hep aynı wav ile:

| Deneme | Sonuç | Anlamı |
|---|---|---|
| H1: Guitar Pro'nun kendi kimliği (UUID) | yüklenmedi | — |
| H2: klasör kayıtları + `Preferences.json` | yüklenmedi | — |
| X1: Guitar Pro dosyası (C), Python ile yeniden zip'lendi | **yüklendi** | Zip paketleme sorun değil |
| X2: C + bizim kimliğimiz | **yüklendi** | **Kimlik kontrol edilmiyor** |
| X3: C, yan dosyalar (stil, görünüm) çıkarıldı | **Guitar Pro çöktü** | C'nin `score.gpif` dosyası `ScoreViews`'a atıf yapıyor |
| Z1 / Z2 / Z3: bizim `score.gpif` X2'nin zip'inde (olduğu gibi / + `ChannelStrip` / padding 0) | **denenmedi** | Dosyalar `~/Documents/gp_probe`'da hazır |

Kimliğin UUID türetimi bulunamadı. Denenen uuid5 ad alanları ve sha1 biçimlerinin hiçbiri tutmadı, ama X2 kimliğin
önemsiz olduğunu gösterdi.

**Senkron sıklığı ölçümü** (019_Vpswc, ses modu; senkrona göre notanın çalacağı an ile kayıttaki başlangıcı arasındaki fark):

| Senkron | ortanca | ≤ 50 ms | ≤ 100 ms | %90 |
|---|---|---|---|---|
| ölçü başına (şu anki yazıcı) | 58 ms | %44.8 | %71.1 | 163 ms |
| **vuruş başına** | **23 ms** | **%80.9** | **%94.9** | 70 ms |

Vuruş başına senkron için Guitar Pro'nun ölçü ortasındaki bir noktayı nasıl yazdığı (`Position` alanı) bilinmiyor; bir
deneme dosyası gerekiyor. Guitar Pro deneme sürümü ~31 Ekim'de bitiyor.

## Ek A — "Tel merkezi" deneyi (26 Ekim 2026; kullanıcı fikri) — KURAL SAĞLANMADI, ürün değişmedi
**Fikir:** Birden çok yerde çalınabilen bir nota, yakındaki **kesin** notaların (tek konumlu ya da modelin ≥ %90 emin
olduğu "çapalar") zaman ağırlıklı perde merkezine çekilir:
`skor = log P_ses(c) − λ·|perde(c) − merkez|`.

Önceki el pozisyonu önselleri (3.6, 3.6b, README22 Adım 4) yalnız önceki notaya bakıyordu; bu varyant çapalar ve zaman
penceresi kullanıyor.
- Kod: `scripts/eval/centroid_strings.py`.
- Log: `docs/results/gv/centroid_strings.log`.
- Kurallar ölçümden önce yazıldı:
  - Ayar **GuitarSet val**'de (çalınan tel) seçilir.
  - Kendi kayıtlarımız yalnız test.
  - GAPS yalnız yazılı tab'a benzerlik.
  - Kabul: GuitarSet'te ≥ +0.02 ve kendi kayıtlarımızda kayıp yok.

| λ, açık tel | GuitarSet (çalınan) | gaps_val / gaps_test (yazılı) | kendi T01 / T02 / E (çalınan, test) |
|---|---|---|---|
| 0 (ürün, akor kısıtsız greedy) | **0.878** | 0.610 / 0.629 | 0.493 / 0.361 / 0.441 |
| 0.5, tarafsız | 0.862 | 0.671 / 0.683 | 0.467 / 0.361 / 0.542 |
| 2, tarafsız | 0.815 | 0.695 / **0.719** | 0.427 / 0.361 / **0.591** |
| 2, açık tel = 0. perde | 0.845 | 0.601 / 0.617 | 0.467 / 0.361 / 0.430 |

(Tam ızgara: λ 0.1–2, pencere 1 / 3 sn, iki açık tel biçimi, logda.)

- **Çalınan tel (GuitarSet) her λ'da düşüyor.** GuitarSet'te seçilen en iyi ayar bile −0.000 → **kabul edilmedi**.
- Yazılı tab'a benzerlik artıyor (0.629 → 0.719) ama edisyon modunun (0.815–0.831) altında kalıyor.
- T02 (aynı nota 3 telde) değişmiyor: bağlam, sesteki tel bilgisinin yerini tutmuyor.
- Kendi E kayıtlarında (1. pozisyon) 0.441 → 0.591. Kazanç açık tel tercihinden geliyor; bu kayıtlar yalnız test ve aynı
  kayıtlarda edisyon zaten 1.000.
- **Sonuç:** Tel merkezi bir çalıcı alışkanlığı önseli. Hangi alışkanlığın geçerli olduğu sesten bilinemiyor.

## Ek B — devlog'a girmemiş önceki ölçümler (23–24 Ekim; ürün değişmedi)
**Dış test özeti** (`docs/results/gv/ext/summary.txt`, `summarize_ext.py`, `candidate.py`; hepsi ürün çözümlemesiyle):

| model | B gerçek F | B görülmeyen tını F | E/F tab bulma | E/F tel ses / edisyon | kendi bulma | T02 tel ses |
|---|---|---|---|---|---|---|
| deep2 (ürün) | 0.824 | 0.851 | 0.858 | 0.569 / 0.822 | 0.554 | 0.361 |
| g1e13 (kontrol) | 0.830 | 0.856 | 0.870 | 0.576 / 0.827 | 0.563 | 0.361 |
| g1s2e15 (kontrol, tohum 2) | 0.830 | 0.855 | 0.871 | 0.578 / 0.827 | 0.565 | 0.333 |
| s1be8 (tını çeşitlendirme) | 0.830 | **0.860** | **0.874** | 0.581 / 0.828 | **0.575** | 0.306 |

Ürüne alınmadı. A/B/C kararı bekliyor (README22 "İkinci aşama").

**YouTube tel verisi** (`scripts/eval/gv/yt_string_labels.py`; veri yalnız yerel, git dışı):
- 2 tur aramayla 380 "her telde 0–12" videosu indirildi (7.1 GB).
- Otomatik etiketleyici kendi T01 kaydımızda **74/74** doğru tel.
- Sonuç: 63 videodan **2209** etiketli nota; tel başına 452 / 207 / 301 / 302 / 433 / 514, 968'i 5. perde ve üstü.

**Tel uzmanı** (`scripts/eval/gv/string_probe.py`, `string_probe*.log`): Ses modelinin donmuş özellikleri (atak + gövde)
ve kendi tel olasılıkları üzerine doğrusal katman; video bazında 5 katlı CV.

| | YouTube CV (tümü / 5.+ perde) | kendi kayıtlar (tümü / 5.+ perde) |
|---|---|---|
| ürün | 0.528 / 0.601 | 0.378 / 0.536 |
| uzman | 0.482 / 0.342 | 0.387 / 0.333 |

Uzman "alçak perdeyi seç" alışkanlığı öğreniyor; net kazanç yok. Donmuş özelliklerde aktarılabilir tel bilgisi yok.

## Sınırlar
- Probe B 87 nota. Kural taklidi bu probla sınırlı. Büyük atlamalar, yüksek pozisyon akorları ve alternatif
  akortlar denenmedi.
- Guitar Pro'nun MusicXML içe aktarımı ile elle nota girişindeki tel kuralı aynı olmayabilir. Yalnızca içe
  aktarma ölçüldü.
- A testindeki BPM (80) ve 4/4 elle verildi, parçanın gerçek değerleri değil. Yalnızca biçim uyumu için.
- Deneme sürümü 7 gün. Sonraki ölçümler bu süreye bağlı.

## Çalıştırma
```
python -m scripts.eval.gp.make_probe                                   # probe B MusicXML (bayt bayt aynı üretilir)
python -m scripts.app.transcribe data/cache/gaps_test/019_Vpswc.npz --bpm 80 --meter 4/4 --mode ses --out A_ours_ses.musicxml
python -m scripts.eval.gp.variant_two_staves A_ours_ses.musicxml A2_onepart.musicxml   # girdi: 4.1 öncesi iki partlı çıktı
python -m scripts.eval.gp.variant_one_staff  A_ours_ses.musicxml A3_onestaff.musicxml
python -m scripts.eval.gp.gpif docs/results/gp/probe/B_pitch_only.gp    # Guitar Pro'nun kaydettiğini çöz
python -m scripts.eval.gp.gp_rule > docs/results/gp/gp_rule.log         # karşılaştırma tabloları
python -m unittest tests.test_gp_rule
```

`docs/results/gp/probe/` içeriği:
- Guitar Pro'nun kaydettiği `.gp` dosyaları: A, A2, A3, B.
- `C_audio_sync.score.gpif`: yalnızca XML. Gömülü GAPS sesi lisans nedeniyle repoya girmez.
- `B_pitch_only.musicxml`.

Repoya girmeyenler:
- Guitar Pro kurulumu.
- Ses bankaları.
- Gömülü sesli `C_audio_sync.gp` (yerelde `~/Documents/gp_probe/`).

## Kaynaklar
- Guitar Pro EULA: https://www.guitar-pro.com/c/9-software-end-user-license-agreement
- GP8 Audio Track: https://www.guitar-pro.com/docs/gp8/audio/backing-track
- GP8 MusicXML içe aktarma: https://www.guitar-pro.com/docs/gp8/import-export/import/import-musicxml-powertab-tabledit
- GP8 polifonik akort aleti: https://www.guitar-pro.com/docs/gp8/tools/tuner
- alphaTab biçimler: https://alphatab.net/docs/category/formats
- GP7 dosya yapısı: https://dev.to/fgm/tip-of-the-day-how-to-compare-guitar-pro-files-474k
- MusicXML tablature: https://www.w3.org/2021/06/musicxml40/tutorial/tablature

## Sıradaki (26 Ekim'de ara verildi; hiçbir şey commit edilmedi)
- 4.2: Z1–Z3 dosyalarını Guitar Pro'da açıp gömülü ses sorununu bulmak; ölçü ortası senkron noktasının `Position`
  biçimi için deneme dosyası; ardından vuruş başına senkron. Guitar Pro denemesi ~31 Ekim'de bitiyor.
- Tel doğruluğu: modelden bağımsız spektral analiz (bilgi seste var mı) ya da sınırı kabul edip tel için edisyon modu.
- A/B/C akustik model kararı (README22).
- Başka uygulamalar da incelenebilir (MuseScore, TuxGuitar, Songsterr, Klangio vb.).
