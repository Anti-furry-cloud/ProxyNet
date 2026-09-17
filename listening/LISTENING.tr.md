**Türkçe** · [English](LISTENING.md)

# Dinleme testi: ağ kesintileri nasıl duyuluyor?

ProxyChat'te henüz sesli sohbet yok. Yapmadan önce, insanların bir konuşmada ne
kadar kesintiye katlanacağını öğrenmek istiyorum. Bu klasördeki kayıtlar
**simülasyon, gerçek görüşme değil.** Ne düşündüğünüzü duymak isterim.

## Klasörde ne var

| Dosya | Ne |
| --- | --- |
| `reference.wav` | Orijinal kayıt, hiç dokunulmamış |
| `sample-A.wav` | Aynı kayıt, simüle edilmiş bir ağdan geçtikten sonra |
| `sample-B.wav` | Aynı |
| `sample-C.wav` | Aynı |

Üç örnek de **aynı** simüle ağdan geçti: aynı anlarda aynı paketler kayboldu ya
da geç geldi. Aralarındaki tek fark, alan tarafın bu paketlerle ne yaptığı.
Hangisinin hangisi olduğunu şimdilik söylemiyorum, adlar duyduğunuzu
etkilemesin diye.

Simüle ağ sentetik. İstatistikleri iki ev internet bağlantısı arasında yapılmış
bir ölçüme uyduruldu. Gerçek bir görüşmenin kaydı değil.

## Nasıl dinlenir

1. Önce `reference.wav` dosyasını dinleyin.
2. Sonra üç örneği istediğiniz sırayla dinleyin. İstediğiniz kadar tekrar
   dinleyebilirsiniz.
3. Mümkünse kulaklık kullanın.

Örnekler gecikme bakımından da farklı olabilir. Gecikme tek başına dinlenen bir
kayıtta duyulmaz, o yüzden yalnızca duyduğunuzu değerlendirin.

## Sorular

1. Her örnek için kesintiler ne kadar rahatsız etti?
   1 = hiç fark etmedim, 5 = konuşmayı takip edemedim.
2. Bu gerçek bir konuşma olsaydı hangi örneği tercih ederdiniz? Neden?
3. Kullandığınız sesli uygulamalarla (Discord, WhatsApp araması, telefon
   görüşmesi vb.) karşılaştırınca her örnekteki kesintiler nasıldı: daha az,
   aşağı yukarı aynı, daha fazla?
4. Kulaklıkla mı hoparlörle mi dinlediniz?
5. Eklemek istediğiniz başka bir şey.

Cevaplarınızı [Discussions](https://github.com/Anti-furry-cloud/ProxyNet/discussions) altındaki **"Listening test"** başlıklı
tartışmaya yazabilirsiniz. İngilizce de yazabilirsiniz.

## Cevaplar neyi değiştirir, neyi değiştirmez

- **Faz 0 v2 kararını değiştirmez.** O kurallar hiçbir v2 ölçümünden önce
  yazıldı ve yayınlandı; görüşleri gördükten sonra değiştirmek amacını boşa
  çıkarırdı. Bkz. `VOICE_CHAT_PLAN.md`.
- Sonraki tasarım kararlarına yön verir: alan taraf kesintiyle gecikme arasında
  nasıl bir denge kurmalı.
- Dinleyenler az sayıda ve kendiliğinden gelen kişiler. Cevapları istatistik
  olarak değil, not olarak okuyacağım.

## Hangi örneğin hangisi olduğunun açıklanması

Hangi harfin hangi sürüme ait olduğunu ayrı bir dosyaya yazdım ve tartışma
kapanana kadar gizli tutuyorum. Dosyanın SHA-256'sı:

```
892abdc6fe8fad450ac32eb5f0fa4469060a47d8b1fc72f6ad8d92e38c61f817
```

Dosyayı yayınladığımda özetinin bu değer olduğunu kontrol edebilirsiniz. Bu,
eşleştirmenin cevaplar geldikten sonra değiştirilmediğini gösterir.

## Kaynak kayıt

Konuşma, O. Henry'nin *The Gift of the Magi* öyküsünün LibriVox kaydından;
okuyan Betsie Bush. LibriVox kayıtları kamu malıdır. Öykünün başından yaklaşık
43 saniye aldım ve 16 kHz mono'ya çevirdim. Okuyana teşekkürler.
