# Golf Score

Een golf-scorekaart voor op de telefoon. Hobbyproject, gebouwd voor eigen gebruik.

**Openen:** https://mv-systems-apps.github.io/golf-score/

---

## Hoe het begon

Met een papieren scorekaart en een pen die het niet deed. Het idee was klein: je scores
invullen op je telefoon in plaats van op papier, zodat je aan het eind van de ronde niet
hoeft te turven.

Daarna kwam de eerste uitbreiding, en die was onvermijdelijk: **stableford**. Als de app
toch je scores kent en weet hoeveel slagen je krijgt, kan hij die punten ook uitrekenen.
Dat scheelt hoofdrekenen op de green.

En zo ging het door. Eenmaal met scores in de app is de volgende vraag altijd: *wat kun je
hier nog meer uit halen?*

- Je **baanhandicap** uitrekenen, zodat je niet met een tabel in de weer hoeft
- Het **dagresultaat** en je **handicap** volgens de WHS-regels
- De rondes bewaren, dus een **archief**
- Als er een archief is, wil je er ook in kunnen zoeken en groeperen
- En met genoeg rondes: **statistieken** — waar verlies je je slagen, wat doen je putts,
  speel je op de ene baan beter dan op de andere

Ergens onderweg kwamen er een tweede speler bij, backups, een regelkaart op je
dagresultaten, en een analyse die zegt wat de cijfers betekenen.

## Wat het is gebleven

Een hobbyproject. Er is geen team, geen planning en geen releasedatum: er komt bij wat
nuttig blijkt op de baan, en wat niet werkt gaat er weer uit.

Dat heeft twee kanten. Het betekent dat elke functie er zit omdat iemand hem echt wilde
gebruiken — maar ook dat het geen product is met ondersteuning. Kom je iets tegen, dan is
een bericht welkom; een toezegging wanneer het opgelost is, niet.

## Hoe het gebouwd is

Volledig met **Claude**, in gesprek — vibe coding. Ik beschrijf wat ik op de baan mis of
wat er niet klopt, Claude analyseert en bouwt, en ik kijk of het werkt zoals bedoeld. Dat
geldt voor de hele app, voor de testsuite eromheen, voor de handleidingen en voor deze
README.

## Wat het niet is

- **Geen officiële handicapregistratie.** De app rekent volgens de WHS-regels, maar je
  officiële handicap loopt via je club en de NGF. Die blijft leidend.
- **Geen account, geen server.** Alles staat in de opslag van je eigen telefoon. Er wordt
  niets verstuurd en er is nergens een kopie — dus maak backups.
- **Geen app uit de store.** Het is een webpagina die je op je beginscherm zet en die
  daarna offline werkt.

## Meer lezen

- **Golf Score - handleiding** — de app van begin tot eind
- **Golf Score - op de iPhone** — wat daar anders gaat dan op Android

Het versienummer staat in de app onder Instellingen → Gegevens → Over Golf Score.
