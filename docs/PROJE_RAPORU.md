# Klasik Gitar Sesinden Otomatik TAB Transkripsiyonu — Proje Raporu

> Kapsam: 26 Ekim 2026'ya kadar yapılan her şey. Ayrıntılar `docs/devlog/README1–23.md` dosyalarında;
> bu rapor onların özetidir. Sayıların hepsi devlog ve `docs/results/` loglarından alınmıştır.
> Projenin iç adlandırması: geliştirme birimi **Katman** (devlog), sunum dosyasındaki deney fazları **Phase 0–5**
> ve mimari bileşenler **Modül 1–8** ayrı eksenlerdir; burada devlog'daki Katman numaraları kullanılır.

## 1. Problem ve hedef

Bir gitar kaydından, her notanın **ne zaman**, **hangi perdede (pitch)**, **hangi telde ve hangi perde numarasında (fret)**
çalındığını bulup okunabilir bir **TAB + nota** çıktısı üretmek. Hedef enstrüman **klasik (naylon telli) gitar**.

Problemin zor tarafları:
- Aynı nota gitarda çoğu zaman 2–4 farklı yerde çalınabilir (ör. E4: açık 1. tel ya da 2. telin 5. perdesi ya da
  3. telin 9. perdesi). Ses bu ayrımı çok zayıf taşır.
- Klasik gitar çok seslidir (akor, arpej, bas + melodi) ve ifadeli çalınır (rubato: tempo esner).
- Tel etiketli klasik gitar verisi yoktur (aşağıda).

## 2. Veri ve değerlendirme ilkeleri

| Veri | Ne | Rolü |
|---|---|---|
| **GuitarSet** | Çelik telli akustik gitar, 6 çalıcı, hexaphonic pikapla **gerçekte çalınan tel** etiketi | Tel denetimi; doğrulama = çalıcı 05 |
| **GAPS v1.1** | 300+ gerçek klasik gitar icrası, hizalı MIDI, MusicXML partisyon (TAB + parmak numarası **yazılı edisyon**) | Klasik gitar nota bulma; edisyon modelinin eğitimi |
| SynthTab (Dev) | Sentetik naylon gitar | Hat doğrulandı; ön-eğitim gerekmedi (kapasite testi, §4.7) |
| Dış testler | İnternet kayıtları + classtab tab'ları, örnek kütüphaneleriyle yeniden sentez, **kendi telefon kayıtlarımız** (tel/perde bilinen egzersizler) | Yalnız test; hiçbir seçime girmez |

Değerlendirme kuralları (bütün proje boyunca):
- **Çalıcıdan bağımsız bölme.** GAPS'in resmi bölmesinde 12 icracı hem eğitimde hem testte → bu icracıların eğitim
  kayıtları çıkarıldı (`--disjoint`): `gaps_fit` 203 / `gaps_val` 28 / `gaps_test` 30 kayıt, ortak icracı yok.
- **Eşik ve parametreler yalnız doğrulamada seçilir**; `gaps_test` yalnızca raporlanır.
- **Alan içi kalibrasyon.** GuitarSet'te seçilen eşikler GAPS'e uymuyor (Katman 3.9'da bulundu); her alan kendi
  doğrulamasında kalibre edilir.
- **GuitarSet sonuçları klasik gitar doğruluğu değildir** (çelik tel). Klasik gitarda gerçekte çalınan teli bilen tek
  veri kendi kayıtlarımızdır (küçük, yalnız test).
- Tek tohumda ±0.01 fark gürültü sayılır. Her adımın kabul kuralı ölçümden **önce** yazılır.

Ölçütler:
- **Nota F1**: başlangıç ±50 ms toleransla nota eşleşmesi (`mir_eval`).
- **Kare F1**: 23 ms'lik karelerde perde.
- **Tab F1**: tel + perde numarası birlikte.
- **Oracle tel doğruluğu**: notalar doğru verildiğinde yalnız tel seçimi.
- **IOI / ölçü içi konum**: ritim ve kuantalama doğruluğu.

## 3. Sistem (bugünkü hali)

```
ses ─► log-CQT (22.05 kHz, hop 512, 192 bin)
     ─► TabCRNN "deep2": derin CNN + BiLSTM; çıkışlar: tel×perde, onset, offset, perde-onset kafası
     ─► Viterbi tabanlı nota çözümleme (onset / yeniden vuruş / enerji kapıları; alan içi kalibrasyon)
     ─► konum: iki AYRI mod
          • "duyulan konum" (ses modu): modelin tel olasılıkları + akor içi tel çakışması kısıtı
          • "klasik edisyon önerisi" (edisyon modu): ses kullanmayan BiLSTM dizi modeli → tel, perde, sol el parmağı
     ─► ritim: BeatNet + DBN vuruş takibi (kullanıcı BPM + ölçü verir ya da vuruşa dokunur) → bağlamlı kuantalayıcı
     ─► MusicXML (nota + TAB) / ASCII TAB / tarayıcıda alphaTab görüntüleyici (naylon gitar sesiyle çalar)
```

Kullanıcı seçenekleri: akort / kapo (`--tuning DADGBE --capo 2`), şarkılı kayıtta vokal ayırma (`--separate mix-vocals`).

## 4. Gelişim kronolojisi

Her alt bölüm: **ne denendi → ne çıktı → karar.**

### 4.1 Katman 0–2: temel ve ilk çalışan hat (Eylül sonu)
- Değiştirmesi pahalı kararlar sabitlendi: ses/CQT ayarları, enstrüman soyutlaması (farklı akort, 4/7 telli),
  ortak nota şeması (`NoteEvent`), GuitarSet edinme.
- Monofonik PitchCNN: kare F1 **0.853** (GuitarSet çalıcı 05). Tel ataması "en düşük perde" kuralıyla.

### 4.2 Katman 3–3.5: gerçek tel / perde tahmini
- TabCNN (tel başına perde sınıflandırması): tab F1 tavanı ~**0.586**. Kayıp teldeydi: perde doğru, tel yanlış.
- Düzeltmeler: sınıf ağırlığı hatası (model sessizliğe çöküyordu), eşik ("sessizlik marjı") taraması, zamansal yumuşatma.
- **CRNN (CNN + BiLSTM)**: zamanı modelleyerek nota ortasındaki tel sıçramalarını azaltmak için.

### 4.3 Katman 3.6 / 3.6b: tel seçimine "gitaristin eli" önseli
- **3.6, el yapımı maliyet:** perde mesafesi + tel atlama + açık tel indirimi, Viterbi ile.
  Gerçek veride katkısız; tarama ağırlığı 0 seçti.
- **3.6b, tablardan öğrenilen önsel:** P(konum | önceki konum, perde), log-lineer.
  - Ses kullanmadan oracle tel doğruluğu: naif 0.206, el yapımı 0.337, **öğrenilen 0.662**.
  - Zayıf CNN'e +0.10 tel doğruluğu kattı.
  - CRNN'e katkısı yok (0.738 → 0.725), çünkü BiLSTM bu bağlamı sesten zaten öğrenmiş.
- **Karar:** CRNN + nota başına tek konum (greedy), tab F1 **0.664**. Darboğaz akustik.

### 4.4 Katman 3.7: veri genişletme (1 Ekim)
- **GuitarSet eşlik (comp) kayıtları eklendi:** oracle tel 0.727 → 0.762, tab F1 0.667.
- **CQT'de perde kaydırma çoğaltması zarar verdi (−0.06).** Kaydırma, tel kimliğini taşıyan tını ile perde arasındaki
  fiziksel ilişkiyi bozuyor.
- **Karar:** GuitarSet mikrofonunda tel ayrımı için azalan getiri.

### 4.5 Katman 3.8: klasik gitara alan uyarlaması (Sunum Phase 3–4)
- **Alan farkı ölçüldü:** GuitarSet'te nota F1 0.86, GAPS'te **0.26**.
- **GAPS ile yalnız perde denetimli ince ayar.** GAPS'te tel etiketi olmadığı için perde olasılığı tel olasılıklarından
  "noisy-OR" ile türetildi.
  - GAPS nota F1 0.255 → **0.360**.
  - Beklenmeyen yan etki: GuitarSet'te tel doğruluğu da arttı (0.762 → 0.797), tab F1 0.697. Daha çok gerçek ses,
    akustik temsili genel olarak güçlendiriyor.

### 4.6 Katman 3.9–3.11: notayı doğru başlatmak ve bitirmek (1–9 Ekim)
- **Hata analizi:** Çok seslide darboğaz tel değil, nota bulmaydı (akorlarda tel hatası %5). Tel hatalarının %98'i komşu
  telde.
- **Onset çıkışı + harmonik istifleme (3.9):**
  - Akorlarda nota F1 0.463 → **0.724**.
  - Oracle tel 0.797 → **0.850**; tab F1 0.739.
  - **Alan içi kalibrasyon** GAPS'i olduğundan kötü göstermeyi düzeltti: taban 0.360 → 0.441, yeni model **0.592**.
- **Çözümleme kuralları ve "mix" ölçütü (3.10):**
  - Eşiği yalnız nota F1'e göre seçmek kare F1'i feda ediyordu; yeni seçim ölçütü (nota F1 + kare F1) / 2.
  - Enerji kuralları ve offset kafası eklendi: GAPS nota F1 **0.689**, tab F1 0.760.
- **Hızlı aynı perde tekrarları (3.11):**
  - Tepe tabanlı çözümleme ve "vadi" hedefli eğitim: 100–200 ms tekrarlarda kaçma −10 puan; tab F1 **0.771**.
  - **<100 ms tekrarlar** hiçbir müdahaleyle değişmedi.

### 4.7 Katman 3.12: kapasite mi, veri mi? (9–10 Ekim)
- **Teşhis:** Eğitim ve doğrulamada aynı hata oranları çıktı (GAPS 0.723 / 0.718). Aşırı öğrenme testinde model etiketleri
  ezberleyebildi (onset 0.952). Yani etiketler öğrenilebilir, sorun model kapasitesi.
- **Çözüm, derin CNN + doğrudan perde-onset kafası ("deep2"):**

  | | önceki | **deep2** |
  |---|---|---|
  | GAPS test nota F1 | 0.720 | **0.779** |
  | GuitarSet tab F1 | 0.771 | **0.777** |
  | oracle tel | 0.869 | **0.878** |

- Kapasite farkı 0.004'e indi, sentetik veri ön-eğitimi (SynthTab) gerekmedi. **deep2 bugünkü akustik model.**

### 4.8 Katman 3.13: klasik gitarda tel — iki ayrı mod (10 Ekim)
- **GAPS partisyonlarından tel etiketi çıkarıldı.** TAB, tekrar açma ve ölçü-saniye eşlemesiyle ses zamanına taşındı.
- **İlk ölçüm:** GuitarSet'te teli seçen model, klasik gitarda "en düşük perde" kuralının bile altında
  (0.610 < 0.702).
- **Partisyon TAB'ıyla ses eğitimi reddedildi.** Görülmemiş icracılara genellenmedi (+0.004), GuitarSet tab F1'i de −0.035
  düşürdü.
  - **Yorum:** Partisyon TAB'ı icracının çaldığı teli değil, editörün **önerdiği** konumu gösteriyor.
- **"Klasik edisyon önerisi" modu kabul edildi.** Ses kullanmayan BiLSTM dizi modeli; tel, perde ve sol el parmağı veriyor.

  | gaps_test | naif kural | edisyon |
  |---|---|---|
  | tel (gerçek notalar) | 0.745 | **0.815** (sonraki sürüm `edition_seq_rec_s2` **0.831**) |
  | parmak (partisyon konumu verilerek) | 0.566 | **0.636** |

- **Ses ve edisyonu karıştırmak reddedildi.** GAPS'te +0.007 getiriyor, ama GuitarSet'te gerçekte çalınan teli 0.878 →
  0.573'e düşürüyor.
- **Karar:** İki mod ayrı. "Duyulan konum" (ses) ve "edisyon önerisi" farklı sorulara cevap veriyor.

### 4.9 Katman 5: ritim, kuantalama, ölçülü TAB (10–13 Ekim; Sunum Modül 5)
- **Bağlamlı kuantalayıcı ("1q") kabul edildi.** Gerçek vuruşla IOI 0.821 → **0.933**.
- **Vuruş takibi en büyük kayıp.**
  - Tam otomatik: vuruş F 0.50. İfadeli klasik müzikte literatürde de zor.
  - **Yarı otomatik mod**, kullanıcı yaklaşık BPM ve ölçü verir: vuruş F **0.631**, uçtan uca IOI **0.695**.
    Hedef 0.833 sağlanmadı; kullanıcı kararıyla bu hâliyle devam edildi.
- **MusicXML yazıcı.** Yazıp geri okuma: 202 partisyon, 159 796 nota **birebir 1.0000**. Ölçü içi konum 0.611.
- **Tap modu**, kullanıcı vuruşa dokunur. Simülasyonda vuruş F **0.976**, ölçü içi konum 0.611 → **0.864**. Gerçek dokunuşla
  doğrulanmadı.

### 4.10 Katman 6: gerçek dünya koşulları (16–17 Ekim)
- **Yapay bozulmalar** (gaps_val nota F1 0.780 tabanına göre):

  | koşul | düşüş |
  |---|---|
  | oda yankısı 0.5 sn | −0.038 |
  | telefon | −0.043 |
  | gürültü 20 dB | −0.031 |
  | şarkı / konuşma 10 dB | −0.096 / −0.090 |

- **Dayanıklılık eğitimi reddedildi** (3 deneme). Bozuk kayıtta kazanç küçüktü; GuitarSet tab F1'de kayıp −0.021'di
  (sınırın iki katı).
- **Vokal ayırma (Demucs, "karışım − vokal") kabul edildi:**

  | koşul | kazanç |
  |---|---|
  | temiz | +0.001 |
  | şarkı 10 dB | **+0.084** |
  | şarkı 0 dB | **+0.243** |

- **Akort / kapo desteği kabul edildi.** Doğru akortla konum doğruluğu ses modunda +0.077, edisyonda +0.084.
- **Çok seslilik sorunu tetiklenmedi.** 3–4 sesli karelerde F1 tek sesten düşük değil.

### 4.11 Katman 5.2 ve notlar: ürünleştirme (17–20 Ekim)
- Şarkılı kayıt seçeneği; edisyon modelinin yeni sürümü (`edition_seq_rec_s2`, tel 0.831); tarayıcıda alphaTab TAB
  görüntüleyicisi.
- **Görüntüleyici sesi düzeltildi.** Piyano yerine CC0 naylon gitar bankası çalıyor; tık ve kırpılma giderildi.
- **İnternetten ilk gerçek kayıt kontrolü** (icracının kendi tab'ı olan bir video):
  - perde F1 0.835
  - aynı tel 0.559
  - bulunan hata türleri: bas notasının yeniden algılanması, açık tel yerine basılı konum seçimi

### 4.12 Kusur haritası ve çözümleme düzeltmeleri (README22, 21–22 Ekim)
- **Farklı gitar sesleriyle test.** 28 test parçası 7 farklı naylon gitar örnek kütüphanesiyle yeniden çalındı:
  nota F1 0.75–0.84. Model GAPS'in tek gitarına aşırı uymamış.
  - Ölçüm hatası düzeltildi: bir kütüphanedeki "büyük oktav sorunu" örnek başındaki sessizlikten çıkmıştı.
- **Gerçek kayıtlar** (internet kayıtları + classtab tab'ları, 23 kayıt): tab notalarının %91'i bulunuyor.
  Tel uyumu ses modunda **%56**, edisyonda %89.
- **Düzeltmeler** (kural "gerçek notayı silen düzeltme yok"; önce gerçek/sahte oranı ölçüldü):

  | düzeltme | etki (gaps_test) |
  |---|---|
  | TAB'da aynı tele iki nota (Viterbi yeniden vuruş kapısı, akor kısıtı, ritim sıkışmasında komşu konum) | 641 → **0** |
  | onset'siz notaya enerji şartı | hayalet notalar 6331 → **4213** |
  | toplam | nota F1 0.779 → **0.818** |

- **"%56" incelemesi:** Ses modu, edisyon ve ikisinin hibrit karışımı ölçüldü.
  - Hibrit hiçbir eşikte edisyonu geçmiyor.
  - GuitarSet'te gerçekte çalınan teli de bozuyor (0.880 → ≤ 0.801).
  - El pozisyonu önseli iki ölçütte de zarar veriyor.
  - **Karar:** "%56" bir hata değil, yazılı edisyona benzerliği ölçüyor. Hibrit mod eklenmedi.
- **Kalan hayalet notaların dökümü:**

  | tür | pay |
  |---|---|
  | parça (bulunmuş notanın yeniden başlaması) | %31 |
  | üst ses | %25 |
  | açık tel / sempatik titreşim | %11 |
  | zamanı kaymış gerçek nota | %9 |
  | etiket boşluğu | %1 |

  "Çoğu etiket hatası" hipotezi zayıf. Üst ses ve açık tel hayaletleri kuralla ayrılamıyor (her eşikte gerçek nota da
  gidiyor), bu yüzden eğitime bırakıldı.

### 4.13 İkinci aşama: eğitim denemeleri ve kendi kayıtlarımız (22–23 Ekim)
- **Aşama 1a: hayalet notaları eğitimde ceza olarak vermek.** Reddedildi; hayaletleri azaltıyor ama gerçek hızlı
  tekrarları da bastırıyor. Aynı ayarla cezasız eğitilen **kontrol modeli** aday oldu:
  - test nota F1 0.818 → **0.824**
  - ikinci tohumla tekrarlandı
- **Aşama 1b: tını çeşitlendirme** (eğitim kayıtları CC0 / CC BY-NC örnek kütüphaneleriyle yeniden çalındı):

  | ölçüt | önce | sonra |
  |---|---|---|
  | görülmeyen tınılarda F | 0.851 | **0.860** |
  | internet kayıtlarında tab bulma | 0.858 | **0.874** |
  | kendi kayıtlarımızda nota bulma | 0.554 | **0.575** |

  Hızlı tekrar kaçma 0.481 ile kabul sınırında; tek tohum.
- **Kendi telefon kayıtlarımız** (yalnız test; tel/perde bilinen egzersizler):

  | kayıt | nota bulma | tel, ses modu | tel, edisyon |
  |---|---|---|---|
  | T01 (her tel 0–12. perde) | 0.962 | 0.507 | 0.453 |
  | T02 (aynı nota 3 farklı telde) | 1.000 | **0.361** (şans ≈ 1/3) | 0.361 |
  | E15 Autumn Leaves | 0.357 | 0.392 | **0.986** |

  **Önemli bulgu:** Ses modu klasik gitarda teli sesten ayıramıyor. GuitarSet'teki 0.88 çelik tel için geçerli,
  klasik gitar için iyimser.
- **Durum:** Ürün modeli değiştirilmedi. A/B/C kararı bekliyor: kontrol modelini almak, 1b'yi ikinci tohumla
  doğrulamak ya da sonraki aşamaya geçmek.

### 4.14 Teli sesten ayırma araştırması (23–24 Ekim)
- **Gerçek gitar tel verisi toplandı.** YouTube'da "her telde 0–12" egzersiz videoları bulundu: 380 video, yalnız yerel
  araştırma, paylaşılmıyor.
  - Otomatik etiketleyici kendi T01 kaydımızda **74/74** doğru tel verdi.
  - Sonuç: 63 videodan **2209** etiketli nota (968'i 5. perde ve üstü).
- **"Tel uzmanı" deneyi.** Ses modelinin donmuş iç özellikleri üzerine doğrusal bir sınıflandırıcı eğitildi; video bazında
  5 katlı çapraz doğrulama yapıldı.

  | | ürün | uzman |
  |---|---|---|
  | YouTube CV | 0.528 | 0.482 |
  | kendi kayıtlarımız | 0.378 | 0.387 |

  - Uzman ya kolay notalarda kazanıp zor notalarda çöküyor ("alçak perdeyi seç" alışkanlığı öğreniyor) ya da tersi.
  - **Negatif sonuç:** Modelin bugünkü özelliklerinde aktarılabilir tel bilgisi yok.

### 4.15 Guitar Pro 8 incelemesi ve çıktı biçimi (24–26 Ekim; README23, Uygulama 4.1 ve 4.2)
- **Yöntem: kara kutu.** Lisans kodun açılmasını yasakladığı için programa kendi girdilerimiz verildi, kaydettiği dosyalar
  incelendi.
- **Guitar Pro'nun tel kuralı çıkarıldı:**
  - Düşük pozisyon tercihi ve komşu notaya göre el kayması. Kendi deneme dosyamızdaki 87 notanın 87'sini aynen tekrarlıyor.
  - Karşılaştırma (gaps_test, gerçek notalar): Guitar Pro kuralı 0.797, **bizim edisyon modelimiz 0.815**.
  - Uçtan uca: 0.777 / **0.803**.
  - Gerçekte çalınan telde (GuitarSet) kural 0.214, ses modu 0.878.
- **MusicXML çıktısı düzeltildi.** Guitar Pro'da tek kanalda nota + TAB görünüyor; alphaTab'da çift çalma önlendi.
  Yazıp geri okuma yine birebir.
- **Doğrudan `.gp` yazıcı (yarım).**
  - Çalışanlar: naylon gitar kanalı (MusicXML'de yapılamıyordu), akort, kapo, bağ, parmak numarası ve ölçü başı senkron
    noktaları Guitar Pro'da doğru okunuyor.
  - Kayıt ilk ölçüden sonra başlıyorsa `FramePadding` gerekiyor; negatif konumu Guitar Pro kırpıyor.
  - **Gömülü ses dosyası Guitar Pro'da henüz yüklenmiyor.** Daraltma: zip biçimi ve ses kimliği sorun değil; kalan
    adaylar `score.gpif` içeriği ve yan dosyalar.
- **Senkron sıklığı ölçümü:** Notaların kayıtla ≤ 100 ms uyumu ölçü başına senkronla %71, **vuruş başına** senkronla
  **%95** (ortanca sapma 58 → 23 ms).

### 4.16 "Tel merkezi" deneyi (26 Ekim)
- **Fikir:** Birden çok yerde çalınabilen notayı, yakındaki kesin notaların ("çapalar": tek konumlu ya da model ≥ %90
  emin) perde merkezine çekmek. Önceki el pozisyonu önselleri yalnız önceki notaya bakıyordu.
- **Kurallar ölçümden önce yazıldı:**
  - Ayar GuitarSet'te (çalınan tel) seçilir.
  - Kendi kayıtlarımız yalnız test.
  - Kabul: ≥ +0.02 ve kendi kayıtlarda kayıp yok.

  | λ (bağlam ağırlığı) | GuitarSet (çalınan) | GAPS test (yazılı) | kendi T02 | kendi E kayıtları |
  |---|---|---|---|---|
  | 0 (ürün) | **0.878** | 0.629 | 0.361 | 0.441 |
  | 2 | 0.815 | 0.719 | 0.361 | 0.591 |

- **Sonuç: kabul edilmedi.**
  - Çalınan tel her ayarda düşüyor.
  - Yazılı tab'a benzerlik artıyor, ama edisyon modunun (0.815–0.831) altında kalıyor.
  - T02 değişmiyor.
  - E kayıtlarındaki kazanç açık tel tercihinden geliyor; bu kayıtlar yalnız test.
  - Tel merkezi bir çalıcı alışkanlığı önseli; hangi alışkanlığın geçerli olduğu sesten bilinemiyor.

## 5. Bugünkü sayılar (özet)

| Ölçüt | Değer | Veri |
|---|---|---|
| Nota F1 (klasik gitar) | **0.818** | GAPS test, ürün (deep2 + çözümleme düzeltmeleri) |
| Kare F1 | 0.693 | GAPS test |
| Tab F1 | 0.777 | **GuitarSet** (çelik tel) çalıcı 05 — klasik gitar sayısı değil |
| Oracle tel doğruluğu, ses modu | 0.878 (GuitarSet) / 0.61–0.63 (GAPS yazılı edisyona göre) / 0.36 (kendi T02, çalınan tel) | |
| Edisyon modu tel uyumu | **0.831** (gerçek notalar), 0.803 (uçtan uca, ilk sürüm) | GAPS test |
| Parmak (edisyon) | 0.636 (partisyon konumuyla) | GAPS test |
| Ritim: uçtan uca IOI / ölçü içi konum | 0.695 / 0.611 (yarı otomatik); 0.877 / 0.864 (tap, simülasyon) | GAPS test |
| Yazıp geri okuma | 1.0000 | 202 partisyon |
| Otomatik testler | 246 | `python -m unittest discover -s tests -t .` |

Akustik modelin gelişimi:
- GuitarSet tab F1: 0.586 (TabCNN) → 0.664 (CRNN) → 0.697 (GAPS uyarlaması) → 0.739 (onset) → 0.771 → **0.777** (deep2).
- GAPS nota F1 (alan içi kalibrasyonla): 0.441 → 0.592 → 0.689 → 0.720 → 0.779 → **0.818**.

## 6. Denenip işe yaramayanlar (bilinçli olarak kayıtta)

| Deneme | Sonuç | Ders |
|---|---|---|
| El yapımı el hareketi maliyeti (3.6) | katkısız | Kural gitaristin gerçek yolunu açıklamıyor |
| Öğrenilen geçiş önseli CRNN üstünde (3.6b, README22) | katkısız / zararlı | BiLSTM bağlamı sesten zaten alıyor |
| CQT perde kaydırma çoğaltması (3.7) | −0.06 | Tel tınısı ile perde ilişkisi bozuluyor |
| Partisyon TAB'ıyla ses eğitimi (3.13) | genellemedi, GuitarSet −0.035 | Yazılı TAB = editör önerisi, çalınan tel değil |
| Ses + edisyon karışımı / hibrit mod (3.13, README22) | çalınan teli bozuyor | İki farklı soru, iki ayrı mod |
| Kayıt koşulu dayanıklılık eğitimi (Katman 6) | temiz kayıpta sınırın 2 katı | Vokal ayırma daha iyi araç |
| <100 ms aynı perde tekrarları (3.10–3.12) | hiçbir müdahale değiştirmedi | Model çözünürlüğü / etiket zamanlaması |
| Hayalet negatifli eğitim (1a) | gerçek tekrarı da bastırıyor | Sahte bölünme ile gerçek tekrar modelde ayrışmıyor |
| Üst ses ve açık tel hayaletleri için kural | her eşikte gerçek nota da gidiyor | Kural değil eğitim gerekiyor |
| Donmuş özelliklerden tel uzmanı | net kazanç yok | Özelliklerde aktarılabilir tel bilgisi yok |
| "Tel merkezi" (çapa notalardan el merkezi, 4.16) | çalınan tel 0.878 → ≤ 0.877 | Bağlam kuralı sesteki tel bilgisinin yerini tutmuyor |
| Guitar Pro'da negatif senkron başlangıcı (4.15) | Guitar Pro kırpıyor | `FramePadding` gerekli |

## 7. Açık sorunlar ve sıradaki adımlar

1. **Klasik gitarda teli sesten ayırmak.** Projenin en büyük açığı (kendi kayıtlarımızda ≈ şans). Seçenekler:
   - modelden bağımsız spektral analiz: bilgi seste var mı?
   - YouTube tel verisiyle uçtan uca ince ayar: pahalı, riskli
   - sınırı kabul edip tel için edisyon modunu önermek
2. **Akustik model kararı (A/B/C):** kontrol modeli ya da tını çeşitlendirmeli model. Ürüne geçmeden önce vuruş ağı yeni
   modele göre yeniden eğitilecek ve GuitarSet tab F1 kontrol edilecek.
3. **Vuruş takibi:** Ritmin ana sınırı; yarı otomatik 0.695, tap modunun tavanı 0.921. Gerçek dokunuşla doğrulama bekliyor.
4. **Kalan hayalet notalar** (parça, üst ses, açık tel) ve **<100 ms tekrarlar:** model düzeyinde iş.
5. **Doğrulama sağlamlığı:** Eşik seçiminde icracıya göre 5 katlı çapraz doğrulama, bootstrap güven aralıkları;
   hatalı hizalanmış `395_w41wc` kaydının eğitimden çıkarılması.
6. **Katman 4 (çalma teknikleri: bend, slide, hammer-on…):** Kendi teknik verimiz hazır olunca.
7. **`.gp` yazıcıyı tamamlamak:** Gömülü ses sorunu ve vuruş başına senkron. Guitar Pro deneme sürümü ~31 Ekim'de
   bitiyor.

**Durum notu (26 Ekim):** Bu rapordaki ve README23'teki işlerin hiçbiri commit edilmedi (kullanıcı kararı). Ürün
doğruluğunu değiştiren bir değişiklik yok: ürün = `tabcrnn_deep2.pt` + `tabcrnn_deep2.cal.json`, gaps_test nota F1
0.818. MusicXML tek kanal düzeltmesi ve `.gp` yazıcı yalnız çıktı biçimini etkiler.

## 8. Sınırlar (dürüstlük notları)
- Klasik gitarda gerçekte çalınan tel yalnız kendi küçük kayıt setimizde ölçüldü; GuitarSet sayıları çelik tel içindir.
- GAPS tel "doğruluğu" yazılı edisyona benzerliktir, icracının çaldığı tel değildir.
- GAPS nota bitişleri partisyondan geldiği için kare F1'in nota sonu kısmı etiket kaynaklı olarak düşük kalır.
- Ritim tap modu sonuçları simülasyondur.
- Bazı kararlar tek tohumla verildi. Tohum farkının ±0.01 olduğu ölçüldü ve kararlarda gürültü payı olarak kullanıldı.
- İnternet ve YouTube verileri yalnız yerel araştırma ve test içindir. Telif nedeniyle paylaşılmaz, eğitime girmez
  (tel uzmanı deneyi hariç; o da ürüne girmedi).
