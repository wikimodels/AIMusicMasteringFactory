# Полная Генеральная Матрица Барочной Музыки (300 Лупов)

Спецификация составлена строго по правилам канона Раннего Барокко (1580–1650):
- **10 томов по 30 лупов** = 300 оригинальных композиций.
- **Инструментальный стандарт:** 100% Chamber Concert Grand (**Yamaha C5 Salamander Piano**) на всех 300 треках.
- **Тональный канон: СТРОГО МИНОР (никаких мажоров):** Dm -> Am -> Gm -> Cm -> Em -> Bm -> F#m -> D Dorian -> C#m -> G Dorian / A Harmonic.
- **8 аутентичных жанров Раннего Барокко в каждом томе:** Pavane Lachrimae (4), Ciaccona/Passacaglia (4), Lamento d'Amour (4), La Folia Antica (4), Sarabande Grave (4), La Monica/Spagnoletta (4), Siciliana / Galliard/Siciliana (3), Toccata/Ricercar (3).
- **Метрическая дифференциация:** Метры **3/4** (Фолия, Чакона, Сарабанда, Гальярда), **4/4** (Павана, Ламенто, Моника, Токката, Ричеркар) и **6/8** (Сицилиана).
- **Ротация 12 стилей клавирного исполнения и фактур (T01–T12):** Style Brisé, Tasto Solo, Chiaroscuro (Эхо), Tirata (Водопады), Suspiratio (Вздохи), Stretto (Канон), Campanella (Колокол), Staccato Portato, Accordo Arpeggiato.
- **Ротация 8 стартов (S01-S08)** и **8 кадансов (C01-C08)**.
- **Хронометраж: строго 30–45 секунд** (темпы 48–64 BPM в зависимости от жанра).
- **Строгий отказ от Пахельбеля:** Гармоническая сетка Пахельбеля исключена как поздний клишированный поп-новодел конца XVII века.

---

## ⚠️ Критические Архитектурные Правила и Запреты (Anti-Patterns for AI Agents)

### 1. Запрет «слепой полутоновой математики» (Причина фальши)
Категорически запрещено вычислять ноты мелодии или баса через произвольные полутоновые смещения (`+1`, `-1`, `+3`, `+5`).
В миноре такие сдвиги порождают тритоны и фальшивые ноты вне лада (например, в Ре миноре `F + 3` дает `G#` — дикий тритон к тонике).
**Правило:** Все ноты и мелодические линии строятся **ИСКЛЮЧИТЕЛЬНО** из ступеней текущего аккорда (`chord_pts`) либо диатонической гаммы лада (`k['scale']`).

### 2. Запрет линейного клиппинга октав (Flat Clamping)
Нельзя ограничивать регистр через `max(60, min(76, p))`. Если нота B5 (83) срезается до 76 (E5), её высотный класс меняется с B на E (грубая фальшь).
**Правило:** Октавный перенос делается строго кратно 12 полутонам:
`while p > high: p -= 12` и `while p < low: p += 12`.

### 3. Синдром «соборного мыла» (Cathedral Mud)
При избыточной соборной реверберации и одновременном ударе 4 голосов на каждой доле микс превращается в кашу.
**Правило:** Максимум 2–3 звучащие ноты одновременно. Голоса перекликаются и дышат (Interlocking Polyphony), а не бьют аккордовыми блоками. Реверберация: `room = 0.65–0.72`, `wet = 0.14–0.18`.

### 4. Устранение пауз без нагромождения и квадратности
Вместо пустых дыр («аккорд-аккорд-пауза») и вместо механического заполнения 16-ми нотами:
- Бас берет половинную ноту (`2n`) на сильной доле, а на половине такта переходит на квинту аккорда или остинато.
- Средний голос раскладывает трезвучие четвертями или восьмыми (Style Brisé).
- Сопрано поёт связную барочную фразу по принципу «Вопрос — Ответ» с обязательными щемящими задержаниями ($4 \to 3$, $7 \to 6$).

### 5. Метрическая природа раннего барокко (Ликвидация «4/4 мыла»)
Категорически запрещено загонять все формы в 4/4!
- **Фолия, Чакона, Сарабанда** пишутся **СТРОГО в 3/4** с акцентом и зависанием на **второй** доле (вздох-цезура).
- **Сицилиана** пишется в **6/8** с колышущейся пунктирной фигурой.
- **Павана, Ламенто, Токката, Ричеркар** пишутся в **4/4**.

### 6. Библиотека исторических моделей Раннего Барокко (Вместо Пахельбеля)
1. **Lamento chromaticum (Passus Duriusculus):** $i \to VII \to VI \to V$ и полутоновый спуск баса ($D \to C\# \to C \to B \to Bb \to A$).
2. **La Folia Antica:** $i \to V \to i \to VII \to III \to VII \to i \to V$ (метр 3/4).
3. **Passamezzo Antico:** $i \to VII \to i \to V \to III \to VII \to i \to V \to i$.
4. **Romanesca:** $III \to VII \to i \to V$.
5. **La Monica (Monicha):** $i \to VII \to III \to VII \to i \to V \to i$.
6. **Spagnoletta:** $i \to iv \to VII \to III \to VI \to ii^\circ \to V \to i$.
7. **Ciaccona Antica:** $i \to v_6 \to iv_6 \to V$ (метр 3/4).
8. **Pavana Lachrimae:** $i \to iv \to V \to i \to VII \to III \to iv \to V$.
9. **Ruggero Antico:** $III \to VII \to i \to V$.

### 7. Спецификация 8 способов старта композиции (S01–S08)
Запрещено начинать все треки однотипно с тяжелой тоники в басу на первой доле. В матрице чередуются 8 контрастных моделей вступления:
* **S01 — Solo Melodic Pickup (Сольный затактовый вздох):** Бас молчит первые 4–8 шагов. Вступает только сопрано (одиночная певучая фраза или восходящий скачок на сексту). Бас мягко подхватывает корень только со 2-й доли или 2-го такта. Эффект: свобода импровизации клавирной фантазии.
* **S02 — First-Inversion Bass (Старт с терцового тона / Секстаккорд):** В басу на первой доле берётся не тоника, а III ступень (в Dm — нота F). Верхний голос берет чистую октаву или квинту. Эффект: мгновенное ощущение полёта и движения вперед без тяжелого «якоря».
* **S03 — Dominant / Leading-Tone Tension (Старт с неустоя):** Трек открывается напряженным доминантовым септаккордом (V) или вводным терцдецимаккордом, разрешающимся в тонику лишь во 2-м такте. Эффект: оперный драматизм Монтеверди.
* **S04 — Imitative Tenor/Alto Entry (Полифонический вброс из середины):** На 1-й доле звучит только средний голос (тенор/альт). На 4–8 шаге сверху вступает сопрано с ответной темой, а бас фундаментом входит последним на 2-м такте. Эффект: канон и ричеркар Фрескобальди.
* **S05 — Silent Downbeat / Syncopated Entry (Пауза на сильную долю):** Первая доля такта абсолютно пустая (тишина/цезура). Мотив вступает со сдвигом на слабую долю (вздох сарабанды). Эффект: аристократическое дыхание.
* **S06 — Subdominant / Mediant Opening (Старт из субдоминанты или параллели):** Пьеса начинается с IV ступени (Gm) или параллельного мажора (F), приходя к основной тонике Dm только к середине 1-й фразы. Эффект: вход в середину повествования (*in medias res*).
* **S07 — Ostinato Pulse First (Остинато баса соло):** Первые 1–2 такта звучит только сухой, ритмичный стаккатный шаг баса или арпеджированный перебор Style Brisé. Мелодия сопрано накрывает гармонию позже. Эффект: театральность чаконы и фолии.
* **S08 — Dotted Rhetorical Question (Пунктирный риторический вызов):** Резкий пунктирный мотив ($8n. + 16n \to 4n$) с мгновенной цезурой (остановкой) на второй половине такта. Эффект: величие увертюры и риторический вопрос оратора.

### 8. Спецификация 8 моделей каданса и зацикливания (C01–C08)
Запрещено заканчивать все треки монолитным тоническим ударом. Каждый финал готовит бесшовный переход в следующий цикл:
* **C01 — Picardy Cadence & Octave Anchor (Пикардийская терция):** Автентическое разрешение ($V \to I$) с мажорной терцией (F# в Dm) и открытым двухголосием в последней доле. Применяется для торжественных паван и ричеркаров.
* **C02 — Half-Cadence Open Question (Половинный каданс-вопрос):** Остановка не на тонике, а на доминанте (V) с чистой квинтой в верхнем голосе и паузой на последних 4 шагах. Создаёт открытый вопрос, естественно толкающий слух в начало лупа.
* **C03 — Deceptive Resolution to VI (Обманный каданс):** Вместо ожидаемого разрешения $V \to I$ бас уходит на VI ступень (Bb в Dm), а мелодия зависает на терции, оставляя глубокое драматическое послевкусие.
* **C04 — Solo Melodic Echo / Unison Fade (Затихающее сольное эхо):** Бас и аккомпанемент замолкают за 4 шага до конца. Последний такт допевает одинокий верхний голос с затухающим velocity ($0.80 \to 0.65$), оставляя чистый реверберационный хвост.
* **C05 — Phrygian Cadence Descent (Фригийский каданс $iv_6 \to V$):** Полутоновый спуск баса на последнюю долю с расходящимся движением мелодии вверх, создающий строгую античную остановку.
* **C06 — Tierce-Free Open Fifth (Пустая открытая квинта / октава):** Финал на чистой квартоквинте без терции ($D2 + A3 + D4$). Архаичное, строгое ренессансное звучание.
* **C07 — Plagal Amen Echo (Плагальный каданс $iv \to i$):** Мягкое созерцательное завершение через субдоминанту ($Gm \to Dm$) с выдержанной тоникой в сопрано без резкого вводного тона.
* **C08 — Anacrusis Loop Bridge (Затактовый мостик в цикл):** На последних 2–4 шагах такта после тихого разрешения звучит короткий мелодический затакт, бесшовно втягивающий слушателя в step 0 следующего круга.

### 9. Спецификация вариаций музыкальных ходов для каждого из 8 стилей
Каждый жанр раннего барокко обладает собственным набором мелодических формул, риторических фигур и типов фактуры:

1. **Pavane Lachrimae (4/4, 50–54 BPM):**
   * *Мелодические ходы:* Нисходящая секундовая кантилена с обязательным задержанием $4 \to 3$ на сильной доле; выразительный скачок вверх на сексту (*Exclamatio*) с последующим плавным заполнением вниз.
   * *Фактура:* Торжественный шагающий бас половинными нотами (`2n`), тихие аккордовые вздохи в среднем голосе на слабую долю.

2. **Ciaccona Antica (3/4, 54–58 BPM):**
   * *Мелодические ходы:* Волнообразные круговые фигуры (*Circulatio*) вокруг квинты аккорда; чередование трёх вариационных пластов (пласт 1 — медленные синкопы; пласт 2 — расслоенные арпеджио Style Brisé восьмыми; пласт 3 — бегущие шестнадцатые).
   * *Фактура:* Непрерывное 4-тактовое остинато баса ($i - v_6 - iv_6 - V$) с акцентированной второй долей.

3. **Lamento d'Amour (4/4, 46–50 BPM):**
   * *Мелодические ходы:* Хроматические скорбные стоны (*Pathopoeia*); задержания $7 \to 6$ и $9 \to 8$, перетягиваемые через тактовую черту; прерывистые мотивы-вздохи (*Suspiratio*) с паузами на сильных долях.
   * *Фактура:* Хроматический спуск баса ($D \to C\# \to C \to B \to Bb \to A$), прозрачное двухголосие, разреженный воздух.

4. **La Folia Antica (3/4, 52–56 BPM):**
   * *Мелодические ходы:* Каноническая фолийная формула (четверть на 1-ю долю $\to$ половинная с акцентом на 2-ю долю); вариации с обострённым вводным тоном $\sharp VII$; пунктирное стаккато на повторах.
   * *Фактура:* Канонический бас Фолии, плотная вторая доля, синкопированное натяжение.

5. **Sarabande Grave (3/4, 48–52 BPM):**
   * *Мелодические ходы:* Широкие интервальные скачки на септиму и октаву с немедленной остановкой на 2-й доле; благородная цезура (*Aposiopesis* — тишина на 3-й доле такта); мелизматическое опевание каданса (мордент).
   * *Фактура:* Глубокая одиночная нота баса на 1-ю долю, мягкий секстаккорд на 2-ю долю, тишина на 3-ю долю.

6. **La Monica & Spagnoletta (4/4, 58–64 BPM):**
   * *Мелодические ходы:* Песенный народный мотив раннего барокко (поступенное восхождение на терцию и плавный волнообразный спуск); парные параллельные терции и сексты; контрастная динамика эхо (2 такта громко $\to$ 2 такта тихо).
   * *Фактура:* Упругий шагающий бас четвертями (`4n` portato/staccato) с октавными скачками в кадансе.

7. **Siciliana (6/8, 56–60 BPM):**
   * *Мелодические ходы:* Характерный сицилианский пунктирный мотив ($8n. + 16n + 8n$); пасторальные секвенции; качающиеся опевания тоники.
   * *Фактура:* Мягкий бас на 1-ю и 4-ю восьмые доли такта, средний голос создаёт непрерывное покачивание лодки (баркарола).

8. **Toccata per l'Elevazione & Ricercar (4/4, 50–56 BPM):**
   * *Мелодические ходы:* Стремительные пассажные взлёты шестнадцатыми (*Tirata*) с неожиданным зависанием на диссонансе над органным басом; строгая полифоническая тема ричеркара с последующей имитацией в басу.
   * *Фактура:* Выдержанный педальный бас (*Tasto solo* на 2 такта) $\to$ взрывной пассаж сопрано $\to$ полифоническое двухголосное стретто.

---

### 10. Теория и архитектура придворных танцев Ренессанса (XVI–XVII вв.) и акустическая физика рояля Yamaha C5

Для достижения подлинного «концертного мирового уровня» в спецификацию закладываются 5 незыблемых теоретических и физических столпов позднего Ренессанса и рубежа раннего Барокко:

1. **Закон парности придворных танцев (*Basse Danse* & *Haute Danse*):**
   * **Низкий танец (Basse danse / Pavane / Passamezzo):** Чётный метр (**4/4**), сдержанный, величавый шаг королей и вельмож без отрыва ног от мрамора. Неторопливый шагающий бас, имитации в среднем регистре.
   * **Высокий танец (Haute danse / Galliard / Saltarello):** Нечётный метр (**3/4** или **6/8**), полётный, устремлённый вверх танец с прыжками (*cinque passi* — пять шагов на 6 долей с прыжком на 5-й доле).
   * **Метрическая пропорция (*Proportio*):** Гальярда и Сальтарелло строятся на той же мелодической теме и басовом остинато, что и предшествующая Павана, трансформируя 4/4 в 3/4.

2. **Модальная ладовая теория (Церковные лады вместо школьного мажор-минора):**
   * **Дорийский лад (*D-Dorian*):** Минор со светлой высокой VI ступенью ($B\natural$ в Dm) — аристократическая, возвышенная меланхолия без сентиментальной плаксивости.
   * **Эолийский лад:** Строгий натуральный античный минор.
   * **Фригийский лад:** Минор с низкой II ступенью — испанское величие и благородная сдержанность.
   * **Гармонический закон консилиума:** Запрет грязных доминантсептаккордов ($V_7$) на сильных долях. Доминанта — строго чистое мажорное трезвучие с полифоническим задержанием $4 \to 3$.

3. **Ритмический феномен гемиолы (*Hemiola*):**
   * В трёхдольных танцах (Гальярда, Куранта) перед кадансом два такта по 3/4 ($3 + 3$) объединяются в три доли по две четверти ($2 + 2 + 2$).
   * На слух метр плавно расширяется, создавая глубокий аристократический реверанс и замедление времени перед финальной клаузулой.

4. **Ренессансные клаузулы (Горизонтальное схождение голосов):**
   * Мелодическая гармония рождается не из блочных аккордов, а из горизонтального пения:
     * *Теноровая клаузула:* плавный шаг вниз $2 \to 1$ ($E \to D$).
     * *Сопрановая клаузула:* задержание $4 \to 3$ и восхождение через вводный полутон $7 \to 8$ ($C\# \to D$).
     * *Финальное разрешение:* либо чистая открытая квинта/октава без терции ($D + A + D$ — кристальная архаика), либо тихая пикардийская терция ($F\#$).

5. **Акустическая физика и исполнение на Yamaha C5 (Salamander Grand):**
   * **Микро-арпеджирование (*Style Brisé* по Фрескобальди 1615 г.):** Категорический запрет одновременного плашмя-удара всех пальцев в одну микросекунду. Бас, средний голос и сопрано вступают с естественным лютневым разбросом в **30–35 мс**. Рояль моментально начинает дышать как под пальцами живого виртуоза.
   * **Шлейф демпфера (Damper Release):** Натуральный спад демпфера **350 мс** вместо цифрового среза нот.
   * **Пространство каменного зала:** Камерная реверберация соборного зала (`room = 0.70–0.72`, `wet = 0.15–0.16`, срез низких частот ниже 35 Гц), сохраняющая прозрачность каждого полифонического голоса. True Peak: строго -1.50 dBFS, битрейт 320 kbps.

---



### 11. Спецификация 12 стилей клавирного исполнения и фактур (T01–T12)

Для преодоления монотонности и создания драматургии в матрице закреплены 9 подлинных исторических стилей игры:

* **T01 — Style Brisé (Лютневое расслоение):** Ноты аккорда расслаиваются по очереди (лютневый перебор, восьмые и шестнадцатые). Создаёт тонкое кружево и интимность.
* **T02 — Tasto Solo / Basso Continuo (Органный пункт):** Монолитный гул глубокого баса (C2), застывающий на 2–3 такта, над которым свободно разворачивается полифония.
* **T03 — Chiaroscuro (Динамическая светотень / Эхо):** 2 такта плотного громкого *Forte* с аккордами $\to$ 2 такта тихого сольного эха *Piano* на октаву выше.
* **T04 — Tirata di Note (Пассажи-водопады):** Стремительные взлёты и каскады шестнадцатых нот (*passaggi*), прорезающие фактуру и врезающиеся в аккорд.
* **T05 — Suspiratio (Прерывистые вздохи скорби):** Паузы на сильных долях, синкопы, перетягивание нот через тактовую черту ($7 \to 6, 4 \to 3$).
* **T06 — Stretto Polyphonico (Канон и перекличка):** Бас начинает тему, через 4 шага её перехватывает тенор, затем сопрано в верхнем регистре внахлёст.
* **T07 — Campanella (Колокольный звон):** Высокая звенящая нота ритмично повторяется на слабую долю, имитируя вечерний колокол часовни.
* **T08 — Staccato Portato (Шагающий церемониальный бас):** Упругие короткие шаги в басу без педали, поверх которых плывёт певучее легато.
* **T09 — Accordo Arpeggiato (Монументальное величие):** Медленные, царственные аккордовые полотна с глубоким перекатом пальцев и задержанием $4 \to 3$.
* **T10 — Groppo & Trillo (Орнаментальные опевания и ренессансные трели):** Виртуозные группетто и тремоло вокруг кадансовых задержаний и вводных тонов (трактат Джироламо Дируты 1593 г. «Трансильванец»). Мелодия закручивается в стремительные 16-е опевания ($4 \to 3$, $\sharp 7 \to 8$), создавая утонченное мерцание.
* **T11 — Cantus Firmus Legatissimo (Хоральная сакральная полифония):** Строгий, молитвенный стиль cantus firmus (школа Яна Свелинка и Самуэля Шейдта). Полный запрет мелких пассажей и арпеджиато. Все голоса поют непрерывным широким легато целыми (`1n`) и половинными (`2n`) нотами, рождая чистейший кристальный соборный резонанс.
* **T12 — Arpeggio Spezzato (Расщеплённое виртуозное арпеджио):** Блестящий стиль итальянского барокко (Бернардо Пасквини, Доменико Скарлатти). Драматические броски с перекрещиванием рук: глубокий бас мгновенно взлетает к звенящему верхнему сопрано через расщепленные ступени трезвучия, создавая эффект сверкающей арфы или двухмануального клавесина.

---

## Том 01: Собрание 1 | Инструмент: Chamber Piano (Yamaha C5)

| # | ID Файла | Форма | Прогрессия / Граунд | Метр | Шаги | Темп | Длит. | Тональность | Стиль игры (T) | Старт (S) | Каданс (C) |
|---|----------|-------|---------------------|------|------|------|-------|-------------|----------------|-----------|------------|
| 001 | Loop_001_Dm_Pavane_T01_S01_C01 | **Pavane** | Lachrimae: i -> iv -> V -> i | 4/4 | 128 | 55 BPM | 38.4s | D Minor | **T01** (Style Brisé (Lute Flow)) | **S01** (Solo Melodic Pickup) | **C01** (Picardy Cadence & Octave Anchor) |
| 002 | Loop_002_Em_Galliard_T06_S06_C08 | **Galliard** | Cinque_Pas: i -> VII -> III -> VII | 3/4 | 144 | 92 BPM | 27.0s | E Minor | **T06** (Stretto (Polyphonic Canon)) | **S06** (Subdominant Opening) | **C08** (Anacrusis Loop Bridge) |
| 003 | Loop_003_Fsm_Lamento_T11_S03_C07 | **Lamento** | Passus_Duriusculus: i -> V6 -> i6 -> iv6 | 4/4 | 128 | 49 BPM | 42.7s | F# Minor | **T11** (Cantus Firmus Legatissimo (Sacred Polyphony)) | **S03** (Dominant Tension Opening) | **C07** (Plagal Amen Echo) |
| 004 | Loop_004_Am_Ciaccona_T04_S08_C06 | **Ciaccona** | Descending_Tetrachord: i -> v6 -> iv6 -> V | 3/4 | 144 | 65 BPM | 36.7s | A Minor | **T04** (Tirata di Note (Cascades)) | **S08** (Dotted Rhetorical Question) | **C06** (Tierce-Free Open Fifth) |
| 005 | Loop_005_Bm_Toccata_T09_S05_C05 | **Toccata** | Elevazione: i -> i -> iv6 -> V | 4/4 | 128 | 82 BPM | 26.9s | B Minor | **T09** (Accordo Arpeggiato (Grandioso)) | **S05** (Silent Downbeat) | **C05** (Phrygian Cadence Descent) |
| 006 | Loop_006_D_Dor_Sarabande_T02_S02_C04 | **Sarabande** | Sarabande_Grave: i -> V -> i -> iv | 3/4 | 144 | 53 BPM | 44.3s | D Dorian Minor | **T02** (Tasto Solo (Pedal Drone)) | **S02** (First-Inversion Bass) | **C04** (Solo Melodic Echo / Fade) |
| 007 | Loop_007_Gm_Canzona_T07_S07_C03 | **Canzona** | Canzona_Francese: i -> iv -> V -> i | 4/4 | 128 | 83 BPM | 26.6s | G Minor | **T07** (Campanella (Bell Chime)) | **S07** (Ostinato Pulse First) | **C03** (Deceptive Resolution to VI) |
| 008 | Loop_008_Cm_Siciliana_T12_S04_C02 | **Siciliana** | Siciliana_Pastorale: i -> iv -> ii_dim -> V | 6/8 | 144 | 55 BPM | 42.8s | C Minor | **T12** (Arpeggio Spezzato (Broken Virtuoso Arpeggio)) | **S04** (Imitative Tenor Entry) | **C02** (Half-Cadence Open Question) |
| 009 | Loop_009_Am_La_Folia_T05_S01_C01 | **La_Folia** | Folia_Antica: i -> V -> i -> VII | 3/4 | 96 | 72 BPM | 23.5s | A Minor | **T05** (Suspiratio (Weeping Sighs)) | **S01** (Solo Melodic Pickup) | **C01** (Picardy Cadence & Octave Anchor) |
| 010 | Loop_010_Bm_Ricercar_T10_S06_C08 | **Ricercar** | Ricercar_Cromatico: i -> v -> i -> iv | 4/4 | 128 | 60 BPM | 35.5s | B Minor | **T10** (Groppo & Trillo (Ornamental Cadences)) | **S06** (Subdominant Opening) | **C08** (Anacrusis Loop Bridge) |
| 011 | Loop_011_D_Dor_La_Monica_T03_S03_C07 | **La_Monica** | Monica_Tradizionale: i -> VII -> III -> VII | 4/4 | 128 | 73 BPM | 29.8s | D Dorian Minor | **T03** (Chiaroscuro (Dynamic Echo)) | **S03** (Dominant Tension Opening) | **C07** (Plagal Amen Echo) |
| 012 | Loop_012_Gm_Spagnoletta_T08_S08_C06 | **Spagnoletta** | Spagnoletta_Antica: i -> iv -> VII -> III | 4/4 | 128 | 69 BPM | 31.3s | G Minor | **T08** (Staccato Portato (Walking Bass)) | **S08** (Dotted Rhetorical Question) | **C06** (Tierce-Free Open Fifth) |
| 013 | Loop_013_Cm_Pavane_T02_S05_C05 | **Pavane** | Passamezzo_Antico: i -> VII -> i -> V | 4/4 | 128 | 52 BPM | 40.4s | C Minor | **T02** (Tasto Solo (Pedal Drone)) | **S05** (Silent Downbeat) | **C05** (Phrygian Cadence Descent) |
| 014 | Loop_014_Dm_Galliard_T07_S02_C04 | **Galliard** | Galliard_Hemiola: i -> III -> VII -> i | 3/4 | 144 | 91 BPM | 27.2s | D Minor | **T07** (Campanella (Bell Chime)) | **S02** (First-Inversion Bass) | **C04** (Solo Melodic Echo / Fade) |
| 015 | Loop_015_Em_Lamento_T12_S07_C03 | **Lamento** | Lamento_d_Arianna: i -> iv -> V -> i | 4/4 | 128 | 46 BPM | 45.2s | E Minor | **T12** (Arpeggio Spezzato (Broken Virtuoso Arpeggio)) | **S07** (Ostinato Pulse First) | **C03** (Deceptive Resolution to VI) |
| 016 | Loop_016_Fsm_Ciaccona_T05_S04_C02 | **Ciaccona** | Romanesca_Ground: III -> VII -> i -> V | 3/4 | 144 | 67 BPM | 35.7s | F# Minor | **T05** (Suspiratio (Weeping Sighs)) | **S04** (Imitative Tenor Entry) | **C02** (Half-Cadence Open Question) |
| 017 | Loop_017_Gm_Toccata_T10_S01_C02 | **Toccata** | Stylus_Phantasticus: i -> iv -> VII -> III | 4/4 | 128 | 81 BPM | 27.2s | G Minor | **T10** (Groppo & Trillo (Ornamental Cadences)) | **S01** (Solo Melodic Pickup) | **C02** (Half-Cadence Open Question) |
| 018 | Loop_018_Cm_Sarabande_T03_S06_C01 | **Sarabande** | Sarabande_Nobiles: i -> i -> iv -> VII | 3/4 | 144 | 50 BPM | 46.7s | C Minor | **T03** (Chiaroscuro (Dynamic Echo)) | **S06** (Subdominant Opening) | **C01** (Picardy Cadence & Octave Anchor) |
| 019 | Loop_019_Dm_Canzona_T08_S03_C08 | **Canzona** | Canzona_di_Galli: i -> V -> VI -> III | 4/4 | 128 | 90 BPM | 24.8s | D Minor | **T08** (Staccato Portato (Walking Bass)) | **S03** (Dominant Tension Opening) | **C08** (Anacrusis Loop Bridge) |
| 020 | Loop_020_Em_Siciliana_T01_S08_C07 | **Siciliana** | Barcarola: i -> v -> i -> iv | 6/8 | 144 | 52 BPM | 45.0s | E Minor | **T01** (Style Brisé (Lute Flow)) | **S08** (Dotted Rhetorical Question) | **C07** (Plagal Amen Echo) |
| 021 | Loop_021_Fsm_La_Folia_T06_S05_C06 | **La_Folia** | Folia_Seconda: III -> VII -> i -> V | 3/4 | 96 | 62 BPM | 26.7s | F# Minor | **T06** (Stretto (Polyphonic Canon)) | **S05** (Silent Downbeat) | **C06** (Tierce-Free Open Fifth) |
| 022 | Loop_022_Am_Ricercar_T11_S02_C05 | **Ricercar** | Ricercar_Antico: i -> i -> iv -> V | 4/4 | 128 | 57 BPM | 37.2s | A Minor | **T11** (Cantus Firmus Legatissimo (Sacred Polyphony)) | **S02** (First-Inversion Bass) | **C05** (Phrygian Cadence Descent) |
| 023 | Loop_023_Bm_La_Monica_T04_S07_C04 | **La_Monica** | Monica_Variata: i -> iv -> VII -> III | 4/4 | 128 | 74 BPM | 29.4s | B Minor | **T04** (Tirata di Note (Cascades)) | **S07** (Ostinato Pulse First) | **C04** (Solo Melodic Echo / Fade) |
| 024 | Loop_024_D_Dor_Spagnoletta_T09_S04_C03 | **Spagnoletta** | Spagnoletta_Saltata: i -> VII -> VI -> V | 4/4 | 128 | 70 BPM | 30.9s | D Dorian Minor | **T09** (Accordo Arpeggiato (Grandioso)) | **S04** (Imitative Tenor Entry) | **C03** (Deceptive Resolution to VI) |
| 025 | Loop_025_Em_Pavane_T03_S02_C02 | **Pavane** | Ploravit: i -> v -> VI -> III | 4/4 | 128 | 56 BPM | 37.8s | E Minor | **T03** (Chiaroscuro (Dynamic Echo)) | **S02** (First-Inversion Bass) | **C02** (Half-Cadence Open Question) |
| 026 | Loop_026_Fsm_Galliard_T08_S07_C01 | **Galliard** | Cinque_Pas: i -> VII -> III -> VII | 3/4 | 144 | 90 BPM | 27.5s | F# Minor | **T08** (Staccato Portato (Walking Bass)) | **S07** (Ostinato Pulse First) | **C01** (Picardy Cadence & Octave Anchor) |
| 027 | Loop_027_Am_Lamento_T01_S04_C08 | **Lamento** | Lamento_Chromaticum: i -> VII -> VI -> V | 4/4 | 128 | 48 BPM | 43.5s | A Minor | **T01** (Style Brisé (Lute Flow)) | **S04** (Imitative Tenor Entry) | **C08** (Anacrusis Loop Bridge) |
| 028 | Loop_028_Bm_Ciaccona_T06_S01_C07 | **Ciaccona** | Ciaccona_di_Paradiso: i -> VII -> VI -> V | 3/4 | 144 | 69 BPM | 34.8s | B Minor | **T06** (Stretto (Polyphonic Canon)) | **S01** (Solo Melodic Pickup) | **C07** (Plagal Amen Echo) |
| 029 | Loop_029_D_Dor_Toccata_T11_S06_C06 | **Toccata** | Elevazione: i -> i -> iv6 -> V | 4/4 | 128 | 80 BPM | 27.5s | D Dorian Minor | **T11** (Cantus Firmus Legatissimo (Sacred Polyphony)) | **S06** (Subdominant Opening) | **C06** (Tierce-Free Open Fifth) |
| 030 | Loop_030_Gm_Sarabande_T04_S03_C05 | **Sarabande** | Sarabande_Grave: i -> V -> i -> iv | 3/4 | 144 | 52 BPM | 45.0s | G Minor | **T04** (Tirata di Note (Cascades)) | **S03** (Dominant Tension Opening) | **C05** (Phrygian Cadence Descent) |

---

## Том 02: Собрание 2 | Инструмент: Chamber Piano (Yamaha C5)

| # | ID Файла | Форма | Прогрессия / Граунд | Метр | Шаги | Темп | Длит. | Тональность | Стиль игры (T) | Старт (S) | Каданс (C) |
|---|----------|-------|---------------------|------|------|------|-------|-------------|----------------|-----------|------------|
| 031 | Loop_031_Cm_Canzona_T09_S08_C04 | **Canzona** | Canzona_di_Galli: i -> V -> VI -> III | 4/4 | 128 | 85 BPM | 26.1s | C Minor | **T09** (Accordo Arpeggiato (Grandioso)) | **S08** (Dotted Rhetorical Question) | **C04** (Solo Melodic Echo / Fade) |
| 032 | Loop_032_Dm_Siciliana_T02_S05_C03 | **Siciliana** | Barcarola: i -> v -> i -> iv | 6/8 | 144 | 52 BPM | 45.0s | D Minor | **T02** (Tasto Solo (Pedal Drone)) | **S05** (Silent Downbeat) | **C03** (Deceptive Resolution to VI) |
| 033 | Loop_033_Bm_La_Folia_T07_S02_C03 | **La_Folia** | Folia_Seconda: III -> VII -> i -> V | 3/4 | 96 | 66 BPM | 25.3s | B Minor | **T07** (Campanella (Bell Chime)) | **S02** (First-Inversion Bass) | **C03** (Deceptive Resolution to VI) |
| 034 | Loop_034_D_Dor_Ricercar_T12_S07_C02 | **Ricercar** | Ricercar_Antico: i -> i -> iv -> V | 4/4 | 128 | 57 BPM | 37.2s | D Dorian Minor | **T12** (Arpeggio Spezzato (Broken Virtuoso Arpeggio)) | **S07** (Ostinato Pulse First) | **C02** (Half-Cadence Open Question) |
| 035 | Loop_035_Gm_La_Monica_T05_S04_C01 | **La_Monica** | Monica_Variata: i -> iv -> VII -> III | 4/4 | 128 | 67 BPM | 32.2s | G Minor | **T05** (Suspiratio (Weeping Sighs)) | **S04** (Imitative Tenor Entry) | **C01** (Picardy Cadence & Octave Anchor) |
| 036 | Loop_036_Cm_Spagnoletta_T10_S01_C08 | **Spagnoletta** | Spagnoletta_Saltata: i -> VII -> VI -> V | 4/4 | 128 | 74 BPM | 29.4s | C Minor | **T10** (Groppo & Trillo (Ornamental Cadences)) | **S01** (Solo Melodic Pickup) | **C08** (Anacrusis Loop Bridge) |
| 037 | Loop_037_Dm_Pavane_T04_S06_C07 | **Pavane** | Lachrimae: i -> iv -> V -> i | 4/4 | 128 | 56 BPM | 37.8s | D Minor | **T04** (Tirata di Note (Cascades)) | **S06** (Subdominant Opening) | **C07** (Plagal Amen Echo) |
| 038 | Loop_038_Em_Galliard_T09_S03_C06 | **Galliard** | Cinque_Pas: i -> VII -> III -> VII | 3/4 | 144 | 92 BPM | 27.0s | E Minor | **T09** (Accordo Arpeggiato (Grandioso)) | **S03** (Dominant Tension Opening) | **C06** (Tierce-Free Open Fifth) |
| 039 | Loop_039_Fsm_Lamento_T02_S08_C05 | **Lamento** | Lamento_d_Arianna: i -> iv -> V -> i | 4/4 | 128 | 48 BPM | 43.5s | F# Minor | **T02** (Tasto Solo (Pedal Drone)) | **S08** (Dotted Rhetorical Question) | **C05** (Phrygian Cadence Descent) |
| 040 | Loop_040_Am_Ciaccona_T07_S05_C04 | **Ciaccona** | Descending_Tetrachord: i -> v6 -> iv6 -> V | 3/4 | 144 | 61 BPM | 38.9s | A Minor | **T07** (Campanella (Bell Chime)) | **S05** (Silent Downbeat) | **C04** (Solo Melodic Echo / Fade) |
| 041 | Loop_041_Cm_Toccata_T12_S02_C03 | **Toccata** | Elevazione: i -> i -> iv6 -> V | 4/4 | 128 | 82 BPM | 26.9s | C Minor | **T12** (Arpeggio Spezzato (Broken Virtuoso Arpeggio)) | **S02** (First-Inversion Bass) | **C03** (Deceptive Resolution to VI) |
| 042 | Loop_042_Dm_Sarabande_T05_S07_C02 | **Sarabande** | Sarabande_Grave: i -> V -> i -> iv | 3/4 | 144 | 52 BPM | 45.0s | D Minor | **T05** (Suspiratio (Weeping Sighs)) | **S07** (Ostinato Pulse First) | **C02** (Half-Cadence Open Question) |
| 043 | Loop_043_Em_Canzona_T10_S04_C01 | **Canzona** | Canzona_Francese: i -> iv -> V -> i | 4/4 | 128 | 92 BPM | 24.4s | E Minor | **T10** (Groppo & Trillo (Ornamental Cadences)) | **S04** (Imitative Tenor Entry) | **C01** (Picardy Cadence & Octave Anchor) |
| 044 | Loop_044_Fsm_Siciliana_T03_S01_C08 | **Siciliana** | Siciliana_Pastorale: i -> iv -> ii_dim -> V | 6/8 | 144 | 56 BPM | 42.1s | F# Minor | **T03** (Chiaroscuro (Dynamic Echo)) | **S01** (Solo Melodic Pickup) | **C08** (Anacrusis Loop Bridge) |
| 045 | Loop_045_Am_La_Folia_T08_S06_C07 | **La_Folia** | Folia_Antica: i -> V -> i -> VII | 3/4 | 96 | 67 BPM | 25.0s | A Minor | **T08** (Staccato Portato (Walking Bass)) | **S06** (Subdominant Opening) | **C07** (Plagal Amen Echo) |
| 046 | Loop_046_Bm_Ricercar_T01_S03_C06 | **Ricercar** | Ricercar_Cromatico: i -> v -> i -> iv | 4/4 | 128 | 54 BPM | 39.1s | B Minor | **T01** (Style Brisé (Lute Flow)) | **S03** (Dominant Tension Opening) | **C06** (Tierce-Free Open Fifth) |
| 047 | Loop_047_D_Dor_La_Monica_T06_S08_C05 | **La_Monica** | Monica_Tradizionale: i -> VII -> III -> VII | 4/4 | 128 | 68 BPM | 31.7s | D Dorian Minor | **T06** (Stretto (Polyphonic Canon)) | **S08** (Dotted Rhetorical Question) | **C05** (Phrygian Cadence Descent) |
| 048 | Loop_048_Gm_Spagnoletta_T11_S05_C04 | **Spagnoletta** | Spagnoletta_Antica: i -> iv -> VII -> III | 4/4 | 128 | 75 BPM | 29.1s | G Minor | **T11** (Cantus Firmus Legatissimo (Sacred Polyphony)) | **S05** (Silent Downbeat) | **C04** (Solo Melodic Echo / Fade) |
| 049 | Loop_049_Fsm_Pavane_T05_S03_C04 | **Pavane** | Passamezzo_Antico: i -> VII -> i -> V | 4/4 | 128 | 53 BPM | 39.7s | F# Minor | **T05** (Suspiratio (Weeping Sighs)) | **S03** (Dominant Tension Opening) | **C04** (Solo Melodic Echo / Fade) |
| 050 | Loop_050_Am_Galliard_T10_S08_C03 | **Galliard** | Galliard_Hemiola: i -> III -> VII -> i | 3/4 | 144 | 91 BPM | 27.2s | A Minor | **T10** (Groppo & Trillo (Ornamental Cadences)) | **S08** (Dotted Rhetorical Question) | **C03** (Deceptive Resolution to VI) |
| 051 | Loop_051_Bm_Lamento_T03_S05_C02 | **Lamento** | Lamento_Chromaticum: i -> VII -> VI -> V | 4/4 | 128 | 50 BPM | 41.9s | B Minor | **T03** (Chiaroscuro (Dynamic Echo)) | **S05** (Silent Downbeat) | **C02** (Half-Cadence Open Question) |
| 052 | Loop_052_D_Dor_Ciaccona_T08_S02_C01 | **Ciaccona** | Romanesca_Ground: III -> VII -> i -> V | 3/4 | 144 | 63 BPM | 37.8s | D Dorian Minor | **T08** (Staccato Portato (Walking Bass)) | **S02** (First-Inversion Bass) | **C01** (Picardy Cadence & Octave Anchor) |
| 053 | Loop_053_Gm_Toccata_T01_S07_C08 | **Toccata** | Stylus_Phantasticus: i -> iv -> VII -> III | 4/4 | 128 | 81 BPM | 27.2s | G Minor | **T01** (Style Brisé (Lute Flow)) | **S07** (Ostinato Pulse First) | **C08** (Anacrusis Loop Bridge) |
| 054 | Loop_054_Cm_Sarabande_T06_S04_C07 | **Sarabande** | Sarabande_Nobiles: i -> i -> iv -> VII | 3/4 | 144 | 54 BPM | 43.5s | C Minor | **T06** (Stretto (Polyphonic Canon)) | **S04** (Imitative Tenor Entry) | **C07** (Plagal Amen Echo) |
| 055 | Loop_055_Dm_Canzona_T11_S01_C06 | **Canzona** | Canzona_di_Galli: i -> V -> VI -> III | 4/4 | 128 | 84 BPM | 26.4s | D Minor | **T11** (Cantus Firmus Legatissimo (Sacred Polyphony)) | **S01** (Solo Melodic Pickup) | **C06** (Tierce-Free Open Fifth) |
| 056 | Loop_056_Em_Siciliana_T04_S06_C05 | **Siciliana** | Barcarola: i -> v -> i -> iv | 6/8 | 144 | 53 BPM | 44.3s | E Minor | **T04** (Tirata di Note (Cascades)) | **S06** (Subdominant Opening) | **C05** (Phrygian Cadence Descent) |
| 057 | Loop_057_D_Dor_La_Folia_T09_S03_C04 | **La_Folia** | Folia_Seconda: III -> VII -> i -> V | 3/4 | 96 | 68 BPM | 24.7s | D Dorian Minor | **T09** (Accordo Arpeggiato (Grandioso)) | **S03** (Dominant Tension Opening) | **C04** (Solo Melodic Echo / Fade) |
| 058 | Loop_058_Gm_Ricercar_T02_S08_C03 | **Ricercar** | Ricercar_Antico: i -> i -> iv -> V | 4/4 | 128 | 58 BPM | 36.6s | G Minor | **T02** (Tasto Solo (Pedal Drone)) | **S08** (Dotted Rhetorical Question) | **C03** (Deceptive Resolution to VI) |
| 059 | Loop_059_Cm_La_Monica_T07_S05_C02 | **La_Monica** | Monica_Variata: i -> iv -> VII -> III | 4/4 | 128 | 69 BPM | 31.3s | C Minor | **T07** (Campanella (Bell Chime)) | **S05** (Silent Downbeat) | **C02** (Half-Cadence Open Question) |
| 060 | Loop_060_Dm_Spagnoletta_T12_S02_C01 | **Spagnoletta** | Spagnoletta_Saltata: i -> VII -> VI -> V | 4/4 | 128 | 76 BPM | 28.8s | D Minor | **T12** (Arpeggio Spezzato (Broken Virtuoso Arpeggio)) | **S02** (First-Inversion Bass) | **C01** (Picardy Cadence & Octave Anchor) |

---

## Том 03: Собрание 3 | Инструмент: Chamber Piano (Yamaha C5)

| # | ID Файла | Форма | Прогрессия / Граунд | Метр | Шаги | Темп | Длит. | Тональность | Стиль игры (T) | Старт (S) | Каданс (C) |
|---|----------|-------|---------------------|------|------|------|-------|-------------|----------------|-----------|------------|
| 061 | Loop_061_Em_Pavane_T06_S07_C08 | **Pavane** | Grand_Pavane: i -> VII -> III -> VI | 4/4 | 128 | 53 BPM | 39.7s | E Minor | **T06** (Stretto (Polyphonic Canon)) | **S07** (Ostinato Pulse First) | **C08** (Anacrusis Loop Bridge) |
| 062 | Loop_062_Fsm_Galliard_T11_S04_C07 | **Galliard** | Galliard_Hemiola: i -> III -> VII -> i | 3/4 | 144 | 93 BPM | 26.7s | F# Minor | **T11** (Cantus Firmus Legatissimo (Sacred Polyphony)) | **S04** (Imitative Tenor Entry) | **C07** (Plagal Amen Echo) |
| 063 | Loop_063_Am_Lamento_T04_S01_C06 | **Lamento** | Lamento_d_Arianna: i -> iv -> V -> i | 4/4 | 128 | 50 BPM | 41.9s | A Minor | **T04** (Tirata di Note (Cascades)) | **S01** (Solo Melodic Pickup) | **C06** (Tierce-Free Open Fifth) |
| 064 | Loop_064_Bm_Ciaccona_T09_S06_C05 | **Ciaccona** | Vitali_Passacaglia: i -> iv6 -> V -> i | 3/4 | 144 | 68 BPM | 35.3s | B Minor | **T09** (Accordo Arpeggiato (Grandioso)) | **S06** (Subdominant Opening) | **C05** (Phrygian Cadence Descent) |
| 065 | Loop_065_Dm_Toccata_T02_S03_C05 | **Toccata** | Stylus_Phantasticus: i -> iv -> VII -> III | 4/4 | 128 | 83 BPM | 26.6s | D Minor | **T02** (Tasto Solo (Pedal Drone)) | **S03** (Dominant Tension Opening) | **C05** (Phrygian Cadence Descent) |
| 066 | Loop_066_Em_Sarabande_T07_S08_C04 | **Sarabande** | Sarabande_Nobiles: i -> i -> iv -> VII | 3/4 | 144 | 54 BPM | 43.5s | E Minor | **T07** (Campanella (Bell Chime)) | **S08** (Dotted Rhetorical Question) | **C04** (Solo Melodic Echo / Fade) |
| 067 | Loop_067_Fsm_Canzona_T12_S05_C03 | **Canzona** | Canzona_di_Galli: i -> V -> VI -> III | 4/4 | 128 | 94 BPM | 23.9s | F# Minor | **T12** (Arpeggio Spezzato (Broken Virtuoso Arpeggio)) | **S05** (Silent Downbeat) | **C03** (Deceptive Resolution to VI) |
| 068 | Loop_068_Am_Siciliana_T05_S02_C02 | **Siciliana** | Barcarola: i -> v -> i -> iv | 6/8 | 144 | 53 BPM | 44.3s | A Minor | **T05** (Suspiratio (Weeping Sighs)) | **S02** (First-Inversion Bass) | **C02** (Half-Cadence Open Question) |
| 069 | Loop_069_Bm_La_Folia_T10_S07_C01 | **La_Folia** | Folia_Seconda: III -> VII -> i -> V | 3/4 | 96 | 72 BPM | 23.5s | B Minor | **T10** (Groppo & Trillo (Ornamental Cadences)) | **S07** (Ostinato Pulse First) | **C01** (Picardy Cadence & Octave Anchor) |
| 070 | Loop_070_D_Dor_Ricercar_T03_S04_C08 | **Ricercar** | Ricercar_Antico: i -> i -> iv -> V | 4/4 | 128 | 58 BPM | 36.6s | D Dorian Minor | **T03** (Chiaroscuro (Dynamic Echo)) | **S04** (Imitative Tenor Entry) | **C08** (Anacrusis Loop Bridge) |
| 071 | Loop_071_Gm_La_Monica_T08_S01_C07 | **La_Monica** | Monica_Variata: i -> iv -> VII -> III | 4/4 | 128 | 73 BPM | 29.8s | G Minor | **T08** (Staccato Portato (Walking Bass)) | **S01** (Solo Melodic Pickup) | **C07** (Plagal Amen Echo) |
| 072 | Loop_072_Cm_Spagnoletta_T01_S06_C06 | **Spagnoletta** | Spagnoletta_Saltata: i -> VII -> VI -> V | 4/4 | 128 | 69 BPM | 31.3s | C Minor | **T01** (Style Brisé (Lute Flow)) | **S06** (Subdominant Opening) | **C06** (Tierce-Free Open Fifth) |
| 073 | Loop_073_Am_Pavane_T07_S04_C05 | **Pavane** | Lachrimae: i -> iv -> V -> i | 4/4 | 128 | 57 BPM | 37.2s | A Minor | **T07** (Campanella (Bell Chime)) | **S04** (Imitative Tenor Entry) | **C05** (Phrygian Cadence Descent) |
| 074 | Loop_074_Bm_Galliard_T12_S01_C04 | **Galliard** | Cinque_Pas: i -> VII -> III -> VII | 3/4 | 144 | 92 BPM | 27.0s | B Minor | **T12** (Arpeggio Spezzato (Broken Virtuoso Arpeggio)) | **S01** (Solo Melodic Pickup) | **C04** (Solo Melodic Echo / Fade) |
| 075 | Loop_075_D_Dor_Lamento_T05_S06_C03 | **Lamento** | Lamento_Chromaticum: i -> VII -> VI -> V | 4/4 | 128 | 47 BPM | 44.4s | D Dorian Minor | **T05** (Suspiratio (Weeping Sighs)) | **S06** (Subdominant Opening) | **C03** (Deceptive Resolution to VI) |
| 076 | Loop_076_Gm_Ciaccona_T10_S03_C02 | **Ciaccona** | Descending_Tetrachord: i -> v6 -> iv6 -> V | 3/4 | 144 | 70 BPM | 34.4s | G Minor | **T10** (Groppo & Trillo (Ornamental Cadences)) | **S03** (Dominant Tension Opening) | **C02** (Half-Cadence Open Question) |
| 077 | Loop_077_Cm_Toccata_T03_S08_C01 | **Toccata** | Elevazione: i -> i -> iv6 -> V | 4/4 | 128 | 82 BPM | 26.9s | C Minor | **T03** (Chiaroscuro (Dynamic Echo)) | **S08** (Dotted Rhetorical Question) | **C01** (Picardy Cadence & Octave Anchor) |
| 078 | Loop_078_Dm_Sarabande_T08_S05_C08 | **Sarabande** | Sarabande_Grave: i -> V -> i -> iv | 3/4 | 144 | 51 BPM | 45.9s | D Minor | **T08** (Staccato Portato (Walking Bass)) | **S05** (Silent Downbeat) | **C08** (Anacrusis Loop Bridge) |
| 079 | Loop_079_Em_Canzona_T01_S02_C07 | **Canzona** | Canzona_Francese: i -> iv -> V -> i | 4/4 | 128 | 86 BPM | 25.8s | E Minor | **T01** (Style Brisé (Lute Flow)) | **S02** (First-Inversion Bass) | **C07** (Plagal Amen Echo) |
| 080 | Loop_080_Fsm_Siciliana_T06_S07_C06 | **Siciliana** | Siciliana_Pastorale: i -> iv -> ii_dim -> V | 6/8 | 144 | 57 BPM | 41.4s | F# Minor | **T06** (Stretto (Polyphonic Canon)) | **S07** (Ostinato Pulse First) | **C06** (Tierce-Free Open Fifth) |
| 081 | Loop_081_Gm_La_Folia_T11_S04_C06 | **La_Folia** | Folia_Antica: i -> V -> i -> VII | 3/4 | 96 | 62 BPM | 26.7s | G Minor | **T11** (Cantus Firmus Legatissimo (Sacred Polyphony)) | **S04** (Imitative Tenor Entry) | **C06** (Tierce-Free Open Fifth) |
| 082 | Loop_082_Cm_Ricercar_T04_S01_C05 | **Ricercar** | Ricercar_Cromatico: i -> v -> i -> iv | 4/4 | 128 | 55 BPM | 38.4s | C Minor | **T04** (Tirata di Note (Cascades)) | **S01** (Solo Melodic Pickup) | **C05** (Phrygian Cadence Descent) |
| 083 | Loop_083_Dm_La_Monica_T09_S06_C04 | **La_Monica** | Monica_Tradizionale: i -> VII -> III -> VII | 4/4 | 128 | 74 BPM | 29.4s | D Minor | **T09** (Accordo Arpeggiato (Grandioso)) | **S06** (Subdominant Opening) | **C04** (Solo Melodic Echo / Fade) |
| 084 | Loop_084_Em_Spagnoletta_T02_S03_C03 | **Spagnoletta** | Spagnoletta_Antica: i -> iv -> VII -> III | 4/4 | 128 | 70 BPM | 30.9s | E Minor | **T02** (Tasto Solo (Pedal Drone)) | **S03** (Dominant Tension Opening) | **C03** (Deceptive Resolution to VI) |
| 085 | Loop_085_Fsm_Pavane_T08_S08_C02 | **Pavane** | Passamezzo_Antico: i -> VII -> i -> V | 4/4 | 128 | 54 BPM | 39.1s | F# Minor | **T08** (Staccato Portato (Walking Bass)) | **S08** (Dotted Rhetorical Question) | **C02** (Half-Cadence Open Question) |
| 086 | Loop_086_Am_Galliard_T01_S05_C01 | **Galliard** | Galliard_Hemiola: i -> III -> VII -> i | 3/4 | 144 | 91 BPM | 27.2s | A Minor | **T01** (Style Brisé (Lute Flow)) | **S05** (Silent Downbeat) | **C01** (Picardy Cadence & Octave Anchor) |
| 087 | Loop_087_Bm_Lamento_T06_S02_C08 | **Lamento** | Passus_Duriusculus: i -> V6 -> i6 -> iv6 | 4/4 | 128 | 49 BPM | 42.7s | B Minor | **T06** (Stretto (Polyphonic Canon)) | **S02** (First-Inversion Bass) | **C08** (Anacrusis Loop Bridge) |
| 088 | Loop_088_D_Dor_Ciaccona_T11_S07_C07 | **Ciaccona** | Romanesca_Ground: III -> VII -> i -> V | 3/4 | 144 | 72 BPM | 33.5s | D Dorian Minor | **T11** (Cantus Firmus Legatissimo (Sacred Polyphony)) | **S07** (Ostinato Pulse First) | **C07** (Plagal Amen Echo) |
| 089 | Loop_089_Em_Toccata_T04_S04_C06 | **Toccata** | Stylus_Phantasticus: i -> iv -> VII -> III | 4/4 | 128 | 81 BPM | 27.2s | E Minor | **T04** (Tirata di Note (Cascades)) | **S04** (Imitative Tenor Entry) | **C06** (Tierce-Free Open Fifth) |
| 090 | Loop_090_Fsm_Sarabande_T09_S01_C05 | **Sarabande** | Sarabande_Nobiles: i -> i -> iv -> VII | 3/4 | 144 | 53 BPM | 44.3s | F# Minor | **T09** (Accordo Arpeggiato (Grandioso)) | **S01** (Solo Melodic Pickup) | **C05** (Phrygian Cadence Descent) |

---

## Том 04: Собрание 4 | Инструмент: Chamber Piano (Yamaha C5)

| # | ID Файла | Форма | Прогрессия / Граунд | Метр | Шаги | Темп | Длит. | Тональность | Стиль игры (T) | Старт (S) | Каданс (C) |
|---|----------|-------|---------------------|------|------|------|-------|-------------|----------------|-----------|------------|
| 091 | Loop_091_Am_Canzona_T02_S06_C04 | **Canzona** | Canzona_Francese: i -> iv -> V -> i | 4/4 | 128 | 81 BPM | 27.2s | A Minor | **T02** (Tasto Solo (Pedal Drone)) | **S06** (Subdominant Opening) | **C04** (Solo Melodic Echo / Fade) |
| 092 | Loop_092_Bm_Siciliana_T07_S03_C03 | **Siciliana** | Siciliana_Pastorale: i -> iv -> ii_dim -> V | 6/8 | 144 | 57 BPM | 41.4s | B Minor | **T07** (Campanella (Bell Chime)) | **S03** (Dominant Tension Opening) | **C03** (Deceptive Resolution to VI) |
| 093 | Loop_093_D_Dor_La_Folia_T12_S08_C02 | **La_Folia** | Folia_Antica: i -> V -> i -> VII | 3/4 | 96 | 66 BPM | 25.3s | D Dorian Minor | **T12** (Arpeggio Spezzato (Broken Virtuoso Arpeggio)) | **S08** (Dotted Rhetorical Question) | **C02** (Half-Cadence Open Question) |
| 094 | Loop_094_Gm_Ricercar_T05_S05_C01 | **Ricercar** | Ricercar_Cromatico: i -> v -> i -> iv | 4/4 | 128 | 55 BPM | 38.4s | G Minor | **T05** (Suspiratio (Weeping Sighs)) | **S05** (Silent Downbeat) | **C01** (Picardy Cadence & Octave Anchor) |
| 095 | Loop_095_Cm_La_Monica_T10_S02_C08 | **La_Monica** | Monica_Tradizionale: i -> VII -> III -> VII | 4/4 | 128 | 67 BPM | 32.2s | C Minor | **T10** (Groppo & Trillo (Ornamental Cadences)) | **S02** (First-Inversion Bass) | **C08** (Anacrusis Loop Bridge) |
| 096 | Loop_096_Dm_Spagnoletta_T03_S07_C07 | **Spagnoletta** | Spagnoletta_Antica: i -> iv -> VII -> III | 4/4 | 128 | 74 BPM | 29.4s | D Minor | **T03** (Chiaroscuro (Dynamic Echo)) | **S07** (Ostinato Pulse First) | **C07** (Plagal Amen Echo) |
| 097 | Loop_097_Bm_Pavane_T09_S05_C07 | **Pavane** | Grand_Pavane: i -> VII -> III -> VI | 4/4 | 128 | 54 BPM | 39.1s | B Minor | **T09** (Accordo Arpeggiato (Grandioso)) | **S05** (Silent Downbeat) | **C07** (Plagal Amen Echo) |
| 098 | Loop_098_D_Dor_Galliard_T02_S02_C06 | **Galliard** | Galliard_Hemiola: i -> III -> VII -> i | 3/4 | 144 | 93 BPM | 26.7s | D Dorian Minor | **T02** (Tasto Solo (Pedal Drone)) | **S02** (First-Inversion Bass) | **C06** (Tierce-Free Open Fifth) |
| 099 | Loop_099_Gm_Lamento_T07_S07_C05 | **Lamento** | Lamento_Chromaticum: i -> VII -> VI -> V | 4/4 | 128 | 49 BPM | 42.7s | G Minor | **T07** (Campanella (Bell Chime)) | **S07** (Ostinato Pulse First) | **C05** (Phrygian Cadence Descent) |
| 100 | Loop_100_Cm_Ciaccona_T12_S04_C04 | **Ciaccona** | Vitali_Passacaglia: i -> iv6 -> V -> i | 3/4 | 144 | 64 BPM | 37.2s | C Minor | **T12** (Arpeggio Spezzato (Broken Virtuoso Arpeggio)) | **S04** (Imitative Tenor Entry) | **C04** (Solo Melodic Echo / Fade) |
| 101 | Loop_101_Dm_Toccata_T05_S01_C03 | **Toccata** | Stylus_Phantasticus: i -> iv -> VII -> III | 4/4 | 128 | 83 BPM | 26.6s | D Minor | **T05** (Suspiratio (Weeping Sighs)) | **S01** (Solo Melodic Pickup) | **C03** (Deceptive Resolution to VI) |
| 102 | Loop_102_Em_Sarabande_T10_S06_C02 | **Sarabande** | Sarabande_Nobiles: i -> i -> iv -> VII | 3/4 | 144 | 53 BPM | 44.3s | E Minor | **T10** (Groppo & Trillo (Ornamental Cadences)) | **S06** (Subdominant Opening) | **C02** (Half-Cadence Open Question) |
| 103 | Loop_103_Fsm_Canzona_T03_S03_C01 | **Canzona** | Canzona_di_Galli: i -> V -> VI -> III | 4/4 | 128 | 88 BPM | 25.3s | F# Minor | **T03** (Chiaroscuro (Dynamic Echo)) | **S03** (Dominant Tension Opening) | **C01** (Picardy Cadence & Octave Anchor) |
| 104 | Loop_104_Am_Siciliana_T08_S08_C08 | **Siciliana** | Barcarola: i -> v -> i -> iv | 6/8 | 144 | 54 BPM | 43.5s | A Minor | **T08** (Staccato Portato (Walking Bass)) | **S08** (Dotted Rhetorical Question) | **C08** (Anacrusis Loop Bridge) |
| 105 | Loop_105_Cm_La_Folia_T01_S05_C07 | **La_Folia** | Folia_Seconda: III -> VII -> i -> V | 3/4 | 96 | 67 BPM | 25.0s | C Minor | **T01** (Style Brisé (Lute Flow)) | **S05** (Silent Downbeat) | **C07** (Plagal Amen Echo) |
| 106 | Loop_106_Dm_Ricercar_T06_S02_C06 | **Ricercar** | Ricercar_Antico: i -> i -> iv -> V | 4/4 | 128 | 59 BPM | 36.0s | D Minor | **T06** (Stretto (Polyphonic Canon)) | **S02** (First-Inversion Bass) | **C06** (Tierce-Free Open Fifth) |
| 107 | Loop_107_Em_La_Monica_T11_S07_C05 | **La_Monica** | Monica_Variata: i -> iv -> VII -> III | 4/4 | 128 | 68 BPM | 31.7s | E Minor | **T11** (Cantus Firmus Legatissimo (Sacred Polyphony)) | **S07** (Ostinato Pulse First) | **C05** (Phrygian Cadence Descent) |
| 108 | Loop_108_Fsm_Spagnoletta_T04_S04_C04 | **Spagnoletta** | Spagnoletta_Saltata: i -> VII -> VI -> V | 4/4 | 128 | 75 BPM | 29.1s | F# Minor | **T04** (Tirata di Note (Cascades)) | **S04** (Imitative Tenor Entry) | **C04** (Solo Melodic Echo / Fade) |
| 109 | Loop_109_Am_Pavane_T10_S01_C03 | **Pavane** | Lachrimae: i -> iv -> V -> i | 4/4 | 128 | 58 BPM | 36.6s | A Minor | **T10** (Groppo & Trillo (Ornamental Cadences)) | **S01** (Solo Melodic Pickup) | **C03** (Deceptive Resolution to VI) |
| 110 | Loop_110_Bm_Galliard_T03_S06_C02 | **Galliard** | Cinque_Pas: i -> VII -> III -> VII | 3/4 | 144 | 92 BPM | 27.0s | B Minor | **T03** (Chiaroscuro (Dynamic Echo)) | **S06** (Subdominant Opening) | **C02** (Half-Cadence Open Question) |
| 111 | Loop_111_D_Dor_Lamento_T08_S03_C01 | **Lamento** | Passus_Duriusculus: i -> V6 -> i6 -> iv6 | 4/4 | 128 | 46 BPM | 45.2s | D Dorian Minor | **T08** (Staccato Portato (Walking Bass)) | **S03** (Dominant Tension Opening) | **C01** (Picardy Cadence & Octave Anchor) |
| 112 | Loop_112_Gm_Ciaccona_T01_S08_C08 | **Ciaccona** | Descending_Tetrachord: i -> v6 -> iv6 -> V | 3/4 | 144 | 66 BPM | 36.2s | G Minor | **T01** (Style Brisé (Lute Flow)) | **S08** (Dotted Rhetorical Question) | **C08** (Anacrusis Loop Bridge) |
| 113 | Loop_113_Fsm_Toccata_T06_S05_C08 | **Toccata** | Elevazione: i -> i -> iv6 -> V | 4/4 | 128 | 82 BPM | 26.9s | F# Minor | **T06** (Stretto (Polyphonic Canon)) | **S05** (Silent Downbeat) | **C08** (Anacrusis Loop Bridge) |
| 114 | Loop_114_Am_Sarabande_T11_S02_C07 | **Sarabande** | Sarabande_Grave: i -> V -> i -> iv | 3/4 | 144 | 50 BPM | 46.7s | A Minor | **T11** (Cantus Firmus Legatissimo (Sacred Polyphony)) | **S02** (First-Inversion Bass) | **C07** (Plagal Amen Echo) |
| 115 | Loop_115_Bm_Canzona_T04_S07_C06 | **Canzona** | Canzona_Francese: i -> iv -> V -> i | 4/4 | 128 | 80 BPM | 27.5s | B Minor | **T04** (Tirata di Note (Cascades)) | **S07** (Ostinato Pulse First) | **C06** (Tierce-Free Open Fifth) |
| 116 | Loop_116_D_Dor_Siciliana_T09_S04_C05 | **Siciliana** | Siciliana_Pastorale: i -> iv -> ii_dim -> V | 6/8 | 144 | 58 BPM | 40.7s | D Dorian Minor | **T09** (Accordo Arpeggiato (Grandioso)) | **S04** (Imitative Tenor Entry) | **C05** (Phrygian Cadence Descent) |
| 117 | Loop_117_Gm_La_Folia_T02_S01_C04 | **La_Folia** | Folia_Antica: i -> V -> i -> VII | 3/4 | 96 | 68 BPM | 24.7s | G Minor | **T02** (Tasto Solo (Pedal Drone)) | **S01** (Solo Melodic Pickup) | **C04** (Solo Melodic Echo / Fade) |
| 118 | Loop_118_Cm_Ricercar_T07_S06_C03 | **Ricercar** | Ricercar_Cromatico: i -> v -> i -> iv | 4/4 | 128 | 56 BPM | 37.8s | C Minor | **T07** (Campanella (Bell Chime)) | **S06** (Subdominant Opening) | **C03** (Deceptive Resolution to VI) |
| 119 | Loop_119_Dm_La_Monica_T12_S03_C02 | **La_Monica** | Monica_Tradizionale: i -> VII -> III -> VII | 4/4 | 128 | 69 BPM | 31.3s | D Minor | **T12** (Arpeggio Spezzato (Broken Virtuoso Arpeggio)) | **S03** (Dominant Tension Opening) | **C02** (Half-Cadence Open Question) |
| 120 | Loop_120_Em_Spagnoletta_T05_S08_C01 | **Spagnoletta** | Spagnoletta_Antica: i -> iv -> VII -> III | 4/4 | 128 | 76 BPM | 28.8s | E Minor | **T05** (Suspiratio (Weeping Sighs)) | **S08** (Dotted Rhetorical Question) | **C01** (Picardy Cadence & Octave Anchor) |

---

## Том 05: Собрание 5 | Инструмент: Chamber Piano (Yamaha C5)

| # | ID Файла | Форма | Прогрессия / Граунд | Метр | Шаги | Темп | Длит. | Тональность | Стиль игры (T) | Старт (S) | Каданс (C) |
|---|----------|-------|---------------------|------|------|------|-------|-------------|----------------|-----------|------------|
| 121 | Loop_121_D_Dor_Pavane_T11_S06_C08 | **Pavane** | Ploravit: i -> v -> VI -> III | 4/4 | 128 | 58 BPM | 36.6s | D Dorian Minor | **T11** (Cantus Firmus Legatissimo (Sacred Polyphony)) | **S06** (Subdominant Opening) | **C08** (Anacrusis Loop Bridge) |
| 122 | Loop_122_Gm_Galliard_T04_S03_C07 | **Galliard** | Cinque_Pas: i -> VII -> III -> VII | 3/4 | 144 | 94 BPM | 26.5s | G Minor | **T04** (Tirata di Note (Cascades)) | **S03** (Dominant Tension Opening) | **C07** (Plagal Amen Echo) |
| 123 | Loop_123_Cm_Lamento_T09_S08_C06 | **Lamento** | Lamento_Chromaticum: i -> VII -> VI -> V | 4/4 | 128 | 46 BPM | 45.2s | C Minor | **T09** (Accordo Arpeggiato (Grandioso)) | **S08** (Dotted Rhetorical Question) | **C06** (Tierce-Free Open Fifth) |
| 124 | Loop_124_Dm_Ciaccona_T02_S05_C05 | **Ciaccona** | Ciaccona_di_Paradiso: i -> VII -> VI -> V | 3/4 | 144 | 71 BPM | 33.9s | D Minor | **T02** (Tasto Solo (Pedal Drone)) | **S05** (Silent Downbeat) | **C05** (Phrygian Cadence Descent) |
| 125 | Loop_125_Em_Toccata_T07_S02_C04 | **Toccata** | Elevazione: i -> i -> iv6 -> V | 4/4 | 128 | 84 BPM | 26.4s | E Minor | **T07** (Campanella (Bell Chime)) | **S02** (First-Inversion Bass) | **C04** (Solo Melodic Echo / Fade) |
| 126 | Loop_126_Fsm_Sarabande_T12_S07_C03 | **Sarabande** | Sarabande_Grave: i -> V -> i -> iv | 3/4 | 144 | 50 BPM | 46.7s | F# Minor | **T12** (Arpeggio Spezzato (Broken Virtuoso Arpeggio)) | **S07** (Ostinato Pulse First) | **C03** (Deceptive Resolution to VI) |
| 127 | Loop_127_Am_Canzona_T05_S04_C02 | **Canzona** | Canzona_Francese: i -> iv -> V -> i | 4/4 | 128 | 90 BPM | 24.8s | A Minor | **T05** (Suspiratio (Weeping Sighs)) | **S04** (Imitative Tenor Entry) | **C02** (Half-Cadence Open Question) |
| 128 | Loop_128_Bm_Siciliana_T10_S01_C01 | **Siciliana** | Siciliana_Pastorale: i -> iv -> ii_dim -> V | 6/8 | 144 | 58 BPM | 40.7s | B Minor | **T10** (Groppo & Trillo (Ornamental Cadences)) | **S01** (Solo Melodic Pickup) | **C01** (Picardy Cadence & Octave Anchor) |
| 129 | Loop_129_Dm_La_Folia_T03_S06_C01 | **La_Folia** | Folia_Antica: i -> V -> i -> VII | 3/4 | 96 | 72 BPM | 23.5s | D Minor | **T03** (Chiaroscuro (Dynamic Echo)) | **S06** (Subdominant Opening) | **C01** (Picardy Cadence & Octave Anchor) |
| 130 | Loop_130_Em_Ricercar_T08_S03_C08 | **Ricercar** | Ricercar_Cromatico: i -> v -> i -> iv | 4/4 | 128 | 56 BPM | 37.8s | E Minor | **T08** (Staccato Portato (Walking Bass)) | **S03** (Dominant Tension Opening) | **C08** (Anacrusis Loop Bridge) |
| 131 | Loop_131_Fsm_La_Monica_T01_S08_C07 | **La_Monica** | Monica_Tradizionale: i -> VII -> III -> VII | 4/4 | 128 | 73 BPM | 29.8s | F# Minor | **T01** (Style Brisé (Lute Flow)) | **S08** (Dotted Rhetorical Question) | **C07** (Plagal Amen Echo) |
| 132 | Loop_132_Am_Spagnoletta_T06_S05_C06 | **Spagnoletta** | Spagnoletta_Antica: i -> iv -> VII -> III | 4/4 | 128 | 69 BPM | 31.3s | A Minor | **T06** (Stretto (Polyphonic Canon)) | **S05** (Silent Downbeat) | **C06** (Tierce-Free Open Fifth) |
| 133 | Loop_133_Bm_Pavane_T12_S02_C05 | **Pavane** | Grand_Pavane: i -> VII -> III -> VI | 4/4 | 128 | 55 BPM | 38.4s | B Minor | **T12** (Arpeggio Spezzato (Broken Virtuoso Arpeggio)) | **S02** (First-Inversion Bass) | **C05** (Phrygian Cadence Descent) |
| 134 | Loop_134_D_Dor_Galliard_T05_S07_C04 | **Galliard** | Galliard_Hemiola: i -> III -> VII -> i | 3/4 | 144 | 93 BPM | 26.7s | D Dorian Minor | **T05** (Suspiratio (Weeping Sighs)) | **S07** (Ostinato Pulse First) | **C04** (Solo Melodic Echo / Fade) |
| 135 | Loop_135_Gm_Lamento_T10_S04_C03 | **Lamento** | Passus_Duriusculus: i -> V6 -> i6 -> iv6 | 4/4 | 128 | 48 BPM | 43.5s | G Minor | **T10** (Groppo & Trillo (Ornamental Cadences)) | **S04** (Imitative Tenor Entry) | **C03** (Deceptive Resolution to VI) |
| 136 | Loop_136_Cm_Ciaccona_T03_S01_C02 | **Ciaccona** | Vitali_Passacaglia: i -> iv6 -> V -> i | 3/4 | 144 | 60 BPM | 39.5s | C Minor | **T03** (Chiaroscuro (Dynamic Echo)) | **S01** (Solo Melodic Pickup) | **C02** (Half-Cadence Open Question) |
| 137 | Loop_137_Am_Toccata_T08_S06_C01 | **Toccata** | Stylus_Phantasticus: i -> iv -> VII -> III | 4/4 | 128 | 83 BPM | 26.6s | A Minor | **T08** (Staccato Portato (Walking Bass)) | **S06** (Subdominant Opening) | **C01** (Picardy Cadence & Octave Anchor) |
| 138 | Loop_138_Bm_Sarabande_T01_S03_C08 | **Sarabande** | Sarabande_Nobiles: i -> i -> iv -> VII | 3/4 | 144 | 52 BPM | 45.0s | B Minor | **T01** (Style Brisé (Lute Flow)) | **S03** (Dominant Tension Opening) | **C08** (Anacrusis Loop Bridge) |
| 139 | Loop_139_D_Dor_Canzona_T06_S08_C07 | **Canzona** | Canzona_di_Galli: i -> V -> VI -> III | 4/4 | 128 | 82 BPM | 26.9s | D Dorian Minor | **T06** (Stretto (Polyphonic Canon)) | **S08** (Dotted Rhetorical Question) | **C07** (Plagal Amen Echo) |
| 140 | Loop_140_Gm_Siciliana_T11_S05_C06 | **Siciliana** | Barcarola: i -> v -> i -> iv | 6/8 | 144 | 55 BPM | 42.8s | G Minor | **T11** (Cantus Firmus Legatissimo (Sacred Polyphony)) | **S05** (Silent Downbeat) | **C06** (Tierce-Free Open Fifth) |
| 141 | Loop_141_Cm_La_Folia_T04_S02_C05 | **La_Folia** | Folia_Seconda: III -> VII -> i -> V | 3/4 | 96 | 62 BPM | 26.7s | C Minor | **T04** (Tirata di Note (Cascades)) | **S02** (First-Inversion Bass) | **C05** (Phrygian Cadence Descent) |
| 142 | Loop_142_Dm_Ricercar_T09_S07_C04 | **Ricercar** | Ricercar_Antico: i -> i -> iv -> V | 4/4 | 128 | 60 BPM | 35.5s | D Minor | **T09** (Accordo Arpeggiato (Grandioso)) | **S07** (Ostinato Pulse First) | **C04** (Solo Melodic Echo / Fade) |
| 143 | Loop_143_Em_La_Monica_T02_S04_C03 | **La_Monica** | Monica_Variata: i -> iv -> VII -> III | 4/4 | 128 | 74 BPM | 29.4s | E Minor | **T02** (Tasto Solo (Pedal Drone)) | **S04** (Imitative Tenor Entry) | **C03** (Deceptive Resolution to VI) |
| 144 | Loop_144_Fsm_Spagnoletta_T07_S01_C02 | **Spagnoletta** | Spagnoletta_Saltata: i -> VII -> VI -> V | 4/4 | 128 | 70 BPM | 30.9s | F# Minor | **T07** (Campanella (Bell Chime)) | **S01** (Solo Melodic Pickup) | **C02** (Half-Cadence Open Question) |
| 145 | Loop_145_Gm_Pavane_T01_S07_C02 | **Pavane** | Lachrimae: i -> iv -> V -> i | 4/4 | 128 | 52 BPM | 40.4s | G Minor | **T01** (Style Brisé (Lute Flow)) | **S07** (Ostinato Pulse First) | **C02** (Half-Cadence Open Question) |
| 146 | Loop_146_Cm_Galliard_T06_S04_C01 | **Galliard** | Cinque_Pas: i -> VII -> III -> VII | 3/4 | 144 | 92 BPM | 27.0s | C Minor | **T06** (Stretto (Polyphonic Canon)) | **S04** (Imitative Tenor Entry) | **C01** (Picardy Cadence & Octave Anchor) |
| 147 | Loop_147_Dm_Lamento_T11_S01_C08 | **Lamento** | Lamento_d_Arianna: i -> iv -> V -> i | 4/4 | 128 | 50 BPM | 41.9s | D Minor | **T11** (Cantus Firmus Legatissimo (Sacred Polyphony)) | **S01** (Solo Melodic Pickup) | **C08** (Anacrusis Loop Bridge) |
| 148 | Loop_148_Em_Ciaccona_T04_S06_C07 | **Ciaccona** | Descending_Tetrachord: i -> v6 -> iv6 -> V | 3/4 | 144 | 62 BPM | 38.3s | E Minor | **T04** (Tirata di Note (Cascades)) | **S06** (Subdominant Opening) | **C07** (Plagal Amen Echo) |
| 149 | Loop_149_Fsm_Toccata_T09_S03_C06 | **Toccata** | Elevazione: i -> i -> iv6 -> V | 4/4 | 128 | 82 BPM | 26.9s | F# Minor | **T09** (Accordo Arpeggiato (Grandioso)) | **S03** (Dominant Tension Opening) | **C06** (Tierce-Free Open Fifth) |
| 150 | Loop_150_Am_Sarabande_T02_S08_C05 | **Sarabande** | Sarabande_Grave: i -> V -> i -> iv | 3/4 | 144 | 54 BPM | 43.5s | A Minor | **T02** (Tasto Solo (Pedal Drone)) | **S08** (Dotted Rhetorical Question) | **C05** (Phrygian Cadence Descent) |

---

## Том 06: Собрание 6 | Инструмент: Chamber Piano (Yamaha C5)

| # | ID Файла | Форма | Прогрессия / Граунд | Метр | Шаги | Темп | Длит. | Тональность | Стиль игры (T) | Старт (S) | Каданс (C) |
|---|----------|-------|---------------------|------|------|------|-------|-------------|----------------|-----------|------------|
| 151 | Loop_151_Bm_Canzona_T07_S05_C04 | **Canzona** | Canzona_di_Galli: i -> V -> VI -> III | 4/4 | 128 | 92 BPM | 24.4s | B Minor | **T07** (Campanella (Bell Chime)) | **S05** (Silent Downbeat) | **C04** (Solo Melodic Echo / Fade) |
| 152 | Loop_152_D_Dor_Siciliana_T12_S02_C03 | **Siciliana** | Barcarola: i -> v -> i -> iv | 6/8 | 144 | 55 BPM | 42.8s | D Dorian Minor | **T12** (Arpeggio Spezzato (Broken Virtuoso Arpeggio)) | **S02** (First-Inversion Bass) | **C03** (Deceptive Resolution to VI) |
| 153 | Loop_153_Em_La_Folia_T05_S07_C02 | **La_Folia** | Folia_Seconda: III -> VII -> i -> V | 3/4 | 96 | 66 BPM | 25.3s | E Minor | **T05** (Suspiratio (Weeping Sighs)) | **S07** (Ostinato Pulse First) | **C02** (Half-Cadence Open Question) |
| 154 | Loop_154_Fsm_Ricercar_T10_S04_C01 | **Ricercar** | Ricercar_Antico: i -> i -> iv -> V | 4/4 | 128 | 60 BPM | 35.5s | F# Minor | **T10** (Groppo & Trillo (Ornamental Cadences)) | **S04** (Imitative Tenor Entry) | **C01** (Picardy Cadence & Octave Anchor) |
| 155 | Loop_155_Am_La_Monica_T03_S01_C08 | **La_Monica** | Monica_Variata: i -> iv -> VII -> III | 4/4 | 128 | 67 BPM | 32.2s | A Minor | **T03** (Chiaroscuro (Dynamic Echo)) | **S01** (Solo Melodic Pickup) | **C08** (Anacrusis Loop Bridge) |
| 156 | Loop_156_Bm_Spagnoletta_T08_S06_C07 | **Spagnoletta** | Spagnoletta_Saltata: i -> VII -> VI -> V | 4/4 | 128 | 74 BPM | 29.4s | B Minor | **T08** (Staccato Portato (Walking Bass)) | **S06** (Subdominant Opening) | **C07** (Plagal Amen Echo) |
| 157 | Loop_157_D_Dor_Pavane_T02_S03_C06 | **Pavane** | Ploravit: i -> v -> VI -> III | 4/4 | 128 | 52 BPM | 40.4s | D Dorian Minor | **T02** (Tasto Solo (Pedal Drone)) | **S03** (Dominant Tension Opening) | **C06** (Tierce-Free Open Fifth) |
| 158 | Loop_158_Gm_Galliard_T07_S08_C05 | **Galliard** | Cinque_Pas: i -> VII -> III -> VII | 3/4 | 144 | 94 BPM | 26.5s | G Minor | **T07** (Campanella (Bell Chime)) | **S08** (Dotted Rhetorical Question) | **C05** (Phrygian Cadence Descent) |
| 159 | Loop_159_Cm_Lamento_T12_S05_C04 | **Lamento** | Passus_Duriusculus: i -> V6 -> i6 -> iv6 | 4/4 | 128 | 50 BPM | 41.9s | C Minor | **T12** (Arpeggio Spezzato (Broken Virtuoso Arpeggio)) | **S05** (Silent Downbeat) | **C04** (Solo Melodic Echo / Fade) |
| 160 | Loop_160_Dm_Ciaccona_T05_S02_C03 | **Ciaccona** | Ciaccona_di_Paradiso: i -> VII -> VI -> V | 3/4 | 144 | 67 BPM | 35.7s | D Minor | **T05** (Suspiratio (Weeping Sighs)) | **S02** (First-Inversion Bass) | **C03** (Deceptive Resolution to VI) |
| 161 | Loop_161_Bm_Toccata_T10_S07_C03 | **Toccata** | Elevazione: i -> i -> iv6 -> V | 4/4 | 128 | 84 BPM | 26.4s | B Minor | **T10** (Groppo & Trillo (Ornamental Cadences)) | **S07** (Ostinato Pulse First) | **C03** (Deceptive Resolution to VI) |
| 162 | Loop_162_D_Dor_Sarabande_T03_S04_C02 | **Sarabande** | Sarabande_Grave: i -> V -> i -> iv | 3/4 | 144 | 54 BPM | 43.5s | D Dorian Minor | **T03** (Chiaroscuro (Dynamic Echo)) | **S04** (Imitative Tenor Entry) | **C02** (Half-Cadence Open Question) |
| 163 | Loop_163_Gm_Canzona_T08_S01_C01 | **Canzona** | Canzona_Francese: i -> iv -> V -> i | 4/4 | 128 | 84 BPM | 26.4s | G Minor | **T08** (Staccato Portato (Walking Bass)) | **S01** (Solo Melodic Pickup) | **C01** (Picardy Cadence & Octave Anchor) |
| 164 | Loop_164_Cm_Siciliana_T01_S06_C08 | **Siciliana** | Siciliana_Pastorale: i -> iv -> ii_dim -> V | 6/8 | 144 | 52 BPM | 45.0s | C Minor | **T01** (Style Brisé (Lute Flow)) | **S06** (Subdominant Opening) | **C08** (Anacrusis Loop Bridge) |
| 165 | Loop_165_Dm_La_Folia_T06_S03_C07 | **La_Folia** | Folia_Antica: i -> V -> i -> VII | 3/4 | 96 | 67 BPM | 25.0s | D Minor | **T06** (Stretto (Polyphonic Canon)) | **S03** (Dominant Tension Opening) | **C07** (Plagal Amen Echo) |
| 166 | Loop_166_Em_Ricercar_T11_S08_C06 | **Ricercar** | Ricercar_Cromatico: i -> v -> i -> iv | 4/4 | 128 | 57 BPM | 37.2s | E Minor | **T11** (Cantus Firmus Legatissimo (Sacred Polyphony)) | **S08** (Dotted Rhetorical Question) | **C06** (Tierce-Free Open Fifth) |
| 167 | Loop_167_Fsm_La_Monica_T04_S05_C05 | **La_Monica** | Monica_Tradizionale: i -> VII -> III -> VII | 4/4 | 128 | 68 BPM | 31.7s | F# Minor | **T04** (Tirata di Note (Cascades)) | **S05** (Silent Downbeat) | **C05** (Phrygian Cadence Descent) |
| 168 | Loop_168_Am_Spagnoletta_T09_S02_C04 | **Spagnoletta** | Spagnoletta_Antica: i -> iv -> VII -> III | 4/4 | 128 | 75 BPM | 29.1s | A Minor | **T09** (Accordo Arpeggiato (Grandioso)) | **S02** (First-Inversion Bass) | **C04** (Solo Melodic Echo / Fade) |
| 169 | Loop_169_Cm_Pavane_T03_S08_C03 | **Pavane** | Grand_Pavane: i -> VII -> III -> VI | 4/4 | 128 | 56 BPM | 37.8s | C Minor | **T03** (Chiaroscuro (Dynamic Echo)) | **S08** (Dotted Rhetorical Question) | **C03** (Deceptive Resolution to VI) |
| 170 | Loop_170_Dm_Galliard_T08_S05_C02 | **Galliard** | Galliard_Hemiola: i -> III -> VII -> i | 3/4 | 144 | 93 BPM | 26.7s | D Minor | **T08** (Staccato Portato (Walking Bass)) | **S05** (Silent Downbeat) | **C02** (Half-Cadence Open Question) |
| 171 | Loop_171_Em_Lamento_T01_S02_C01 | **Lamento** | Lamento_d_Arianna: i -> iv -> V -> i | 4/4 | 128 | 47 BPM | 44.4s | E Minor | **T01** (Style Brisé (Lute Flow)) | **S02** (First-Inversion Bass) | **C01** (Picardy Cadence & Octave Anchor) |
| 172 | Loop_172_Fsm_Ciaccona_T06_S07_C08 | **Ciaccona** | Vitali_Passacaglia: i -> iv6 -> V -> i | 3/4 | 144 | 69 BPM | 34.8s | F# Minor | **T06** (Stretto (Polyphonic Canon)) | **S07** (Ostinato Pulse First) | **C08** (Anacrusis Loop Bridge) |
| 173 | Loop_173_Am_Toccata_T11_S04_C07 | **Toccata** | Stylus_Phantasticus: i -> iv -> VII -> III | 4/4 | 128 | 83 BPM | 26.6s | A Minor | **T11** (Cantus Firmus Legatissimo (Sacred Polyphony)) | **S04** (Imitative Tenor Entry) | **C07** (Plagal Amen Echo) |
| 174 | Loop_174_Bm_Sarabande_T04_S01_C06 | **Sarabande** | Sarabande_Nobiles: i -> i -> iv -> VII | 3/4 | 144 | 51 BPM | 45.9s | B Minor | **T04** (Tirata di Note (Cascades)) | **S01** (Solo Melodic Pickup) | **C06** (Tierce-Free Open Fifth) |
| 175 | Loop_175_D_Dor_Canzona_T09_S06_C05 | **Canzona** | Canzona_di_Galli: i -> V -> VI -> III | 4/4 | 128 | 91 BPM | 24.6s | D Dorian Minor | **T09** (Accordo Arpeggiato (Grandioso)) | **S06** (Subdominant Opening) | **C05** (Phrygian Cadence Descent) |
| 176 | Loop_176_Gm_Siciliana_T02_S03_C04 | **Siciliana** | Barcarola: i -> v -> i -> iv | 6/8 | 144 | 56 BPM | 42.1s | G Minor | **T02** (Tasto Solo (Pedal Drone)) | **S03** (Dominant Tension Opening) | **C04** (Solo Melodic Echo / Fade) |
| 177 | Loop_177_Fsm_La_Folia_T07_S08_C04 | **La_Folia** | Folia_Seconda: III -> VII -> i -> V | 3/4 | 96 | 68 BPM | 24.7s | F# Minor | **T07** (Campanella (Bell Chime)) | **S08** (Dotted Rhetorical Question) | **C04** (Solo Melodic Echo / Fade) |
| 178 | Loop_178_Am_Ricercar_T12_S05_C03 | **Ricercar** | Ricercar_Antico: i -> i -> iv -> V | 4/4 | 128 | 54 BPM | 39.1s | A Minor | **T12** (Arpeggio Spezzato (Broken Virtuoso Arpeggio)) | **S05** (Silent Downbeat) | **C03** (Deceptive Resolution to VI) |
| 179 | Loop_179_Bm_La_Monica_T05_S02_C02 | **La_Monica** | Monica_Variata: i -> iv -> VII -> III | 4/4 | 128 | 69 BPM | 31.3s | B Minor | **T05** (Suspiratio (Weeping Sighs)) | **S02** (First-Inversion Bass) | **C02** (Half-Cadence Open Question) |
| 180 | Loop_180_D_Dor_Spagnoletta_T10_S07_C01 | **Spagnoletta** | Spagnoletta_Saltata: i -> VII -> VI -> V | 4/4 | 128 | 76 BPM | 28.8s | D Dorian Minor | **T10** (Groppo & Trillo (Ornamental Cadences)) | **S07** (Ostinato Pulse First) | **C01** (Picardy Cadence & Octave Anchor) |

---

## Том 07: Собрание 7 | Инструмент: Chamber Piano (Yamaha C5)

| # | ID Файла | Форма | Прогрессия / Граунд | Метр | Шаги | Темп | Длит. | Тональность | Стиль игры (T) | Старт (S) | Каданс (C) |
|---|----------|-------|---------------------|------|------|------|-------|-------------|----------------|-----------|------------|
| 181 | Loop_181_Gm_Pavane_T04_S04_C08 | **Pavane** | Passamezzo_Antico: i -> VII -> i -> V | 4/4 | 128 | 56 BPM | 37.8s | G Minor | **T04** (Tirata di Note (Cascades)) | **S04** (Imitative Tenor Entry) | **C08** (Anacrusis Loop Bridge) |
| 182 | Loop_182_Cm_Galliard_T09_S01_C07 | **Galliard** | Galliard_Hemiola: i -> III -> VII -> i | 3/4 | 144 | 95 BPM | 26.2s | C Minor | **T09** (Accordo Arpeggiato (Grandioso)) | **S01** (Solo Melodic Pickup) | **C07** (Plagal Amen Echo) |
| 183 | Loop_183_Dm_Lamento_T02_S06_C06 | **Lamento** | Passus_Duriusculus: i -> V6 -> i6 -> iv6 | 4/4 | 128 | 47 BPM | 44.4s | D Minor | **T02** (Tasto Solo (Pedal Drone)) | **S06** (Subdominant Opening) | **C06** (Tierce-Free Open Fifth) |
| 184 | Loop_184_Em_Ciaccona_T07_S03_C05 | **Ciaccona** | Romanesca_Ground: III -> VII -> i -> V | 3/4 | 144 | 61 BPM | 38.9s | E Minor | **T07** (Campanella (Bell Chime)) | **S03** (Dominant Tension Opening) | **C05** (Phrygian Cadence Descent) |
| 185 | Loop_185_D_Dor_Toccata_T12_S08_C04 | **Toccata** | Stylus_Phantasticus: i -> iv -> VII -> III | 4/4 | 128 | 85 BPM | 26.1s | D Dorian Minor | **T12** (Arpeggio Spezzato (Broken Virtuoso Arpeggio)) | **S08** (Dotted Rhetorical Question) | **C04** (Solo Melodic Echo / Fade) |
| 186 | Loop_186_Gm_Sarabande_T05_S05_C03 | **Sarabande** | Sarabande_Nobiles: i -> i -> iv -> VII | 3/4 | 144 | 51 BPM | 45.9s | G Minor | **T05** (Suspiratio (Weeping Sighs)) | **S05** (Silent Downbeat) | **C03** (Deceptive Resolution to VI) |
| 187 | Loop_187_Cm_Canzona_T10_S02_C02 | **Canzona** | Canzona_di_Galli: i -> V -> VI -> III | 4/4 | 128 | 86 BPM | 25.8s | C Minor | **T10** (Groppo & Trillo (Ornamental Cadences)) | **S02** (First-Inversion Bass) | **C02** (Half-Cadence Open Question) |
| 188 | Loop_188_Dm_Siciliana_T03_S07_C01 | **Siciliana** | Barcarola: i -> v -> i -> iv | 6/8 | 144 | 56 BPM | 42.1s | D Minor | **T03** (Chiaroscuro (Dynamic Echo)) | **S07** (Ostinato Pulse First) | **C01** (Picardy Cadence & Octave Anchor) |
| 189 | Loop_189_Em_La_Folia_T08_S04_C08 | **La_Folia** | Folia_Seconda: III -> VII -> i -> V | 3/4 | 96 | 72 BPM | 23.5s | E Minor | **T08** (Staccato Portato (Walking Bass)) | **S04** (Imitative Tenor Entry) | **C08** (Anacrusis Loop Bridge) |
| 190 | Loop_190_Fsm_Ricercar_T01_S01_C07 | **Ricercar** | Ricercar_Antico: i -> i -> iv -> V | 4/4 | 128 | 54 BPM | 39.1s | F# Minor | **T01** (Style Brisé (Lute Flow)) | **S01** (Solo Melodic Pickup) | **C07** (Plagal Amen Echo) |
| 191 | Loop_191_Am_La_Monica_T06_S06_C06 | **La_Monica** | Monica_Variata: i -> iv -> VII -> III | 4/4 | 128 | 73 BPM | 29.8s | A Minor | **T06** (Stretto (Polyphonic Canon)) | **S06** (Subdominant Opening) | **C06** (Tierce-Free Open Fifth) |
| 192 | Loop_192_Bm_Spagnoletta_T11_S03_C05 | **Spagnoletta** | Spagnoletta_Saltata: i -> VII -> VI -> V | 4/4 | 128 | 69 BPM | 31.3s | B Minor | **T11** (Cantus Firmus Legatissimo (Sacred Polyphony)) | **S03** (Dominant Tension Opening) | **C05** (Phrygian Cadence Descent) |
| 193 | Loop_193_Dm_Pavane_T05_S01_C05 | **Pavane** | Ploravit: i -> v -> VI -> III | 4/4 | 128 | 53 BPM | 39.7s | D Minor | **T05** (Suspiratio (Weeping Sighs)) | **S01** (Solo Melodic Pickup) | **C05** (Phrygian Cadence Descent) |
| 194 | Loop_194_Em_Galliard_T10_S06_C04 | **Galliard** | Cinque_Pas: i -> VII -> III -> VII | 3/4 | 144 | 94 BPM | 26.5s | E Minor | **T10** (Groppo & Trillo (Ornamental Cadences)) | **S06** (Subdominant Opening) | **C04** (Solo Melodic Echo / Fade) |
| 195 | Loop_195_Fsm_Lamento_T03_S03_C03 | **Lamento** | Lamento_d_Arianna: i -> iv -> V -> i | 4/4 | 128 | 49 BPM | 42.7s | F# Minor | **T03** (Chiaroscuro (Dynamic Echo)) | **S03** (Dominant Tension Opening) | **C03** (Deceptive Resolution to VI) |
| 196 | Loop_196_Am_Ciaccona_T08_S08_C02 | **Ciaccona** | Ciaccona_di_Paradiso: i -> VII -> VI -> V | 3/4 | 144 | 63 BPM | 37.8s | A Minor | **T08** (Staccato Portato (Walking Bass)) | **S08** (Dotted Rhetorical Question) | **C02** (Half-Cadence Open Question) |
| 197 | Loop_197_Bm_Toccata_T01_S05_C01 | **Toccata** | Elevazione: i -> i -> iv6 -> V | 4/4 | 128 | 84 BPM | 26.4s | B Minor | **T01** (Style Brisé (Lute Flow)) | **S05** (Silent Downbeat) | **C01** (Picardy Cadence & Octave Anchor) |
| 198 | Loop_198_D_Dor_Sarabande_T06_S02_C08 | **Sarabande** | Sarabande_Grave: i -> V -> i -> iv | 3/4 | 144 | 53 BPM | 44.3s | D Dorian Minor | **T06** (Stretto (Polyphonic Canon)) | **S02** (First-Inversion Bass) | **C08** (Anacrusis Loop Bridge) |
| 199 | Loop_199_Gm_Canzona_T11_S07_C07 | **Canzona** | Canzona_Francese: i -> iv -> V -> i | 4/4 | 128 | 93 BPM | 24.1s | G Minor | **T11** (Cantus Firmus Legatissimo (Sacred Polyphony)) | **S07** (Ostinato Pulse First) | **C07** (Plagal Amen Echo) |
| 200 | Loop_200_Cm_Siciliana_T04_S04_C06 | **Siciliana** | Siciliana_Pastorale: i -> iv -> ii_dim -> V | 6/8 | 144 | 53 BPM | 44.3s | C Minor | **T04** (Tirata di Note (Cascades)) | **S04** (Imitative Tenor Entry) | **C06** (Tierce-Free Open Fifth) |
| 201 | Loop_201_Am_La_Folia_T09_S01_C05 | **La_Folia** | Folia_Antica: i -> V -> i -> VII | 3/4 | 96 | 62 BPM | 26.7s | A Minor | **T09** (Accordo Arpeggiato (Grandioso)) | **S01** (Solo Melodic Pickup) | **C05** (Phrygian Cadence Descent) |
| 202 | Loop_202_Bm_Ricercar_T02_S06_C04 | **Ricercar** | Ricercar_Cromatico: i -> v -> i -> iv | 4/4 | 128 | 58 BPM | 36.6s | B Minor | **T02** (Tasto Solo (Pedal Drone)) | **S06** (Subdominant Opening) | **C04** (Solo Melodic Echo / Fade) |
| 203 | Loop_203_D_Dor_La_Monica_T07_S03_C03 | **La_Monica** | Monica_Tradizionale: i -> VII -> III -> VII | 4/4 | 128 | 74 BPM | 29.4s | D Dorian Minor | **T07** (Campanella (Bell Chime)) | **S03** (Dominant Tension Opening) | **C03** (Deceptive Resolution to VI) |
| 204 | Loop_204_Gm_Spagnoletta_T12_S08_C02 | **Spagnoletta** | Spagnoletta_Antica: i -> iv -> VII -> III | 4/4 | 128 | 70 BPM | 30.9s | G Minor | **T12** (Arpeggio Spezzato (Broken Virtuoso Arpeggio)) | **S08** (Dotted Rhetorical Question) | **C02** (Half-Cadence Open Question) |
| 205 | Loop_205_Cm_Pavane_T06_S05_C01 | **Pavane** | Grand_Pavane: i -> VII -> III -> VI | 4/4 | 128 | 57 BPM | 37.2s | C Minor | **T06** (Stretto (Polyphonic Canon)) | **S05** (Silent Downbeat) | **C01** (Picardy Cadence & Octave Anchor) |
| 206 | Loop_206_Dm_Galliard_T11_S02_C08 | **Galliard** | Galliard_Hemiola: i -> III -> VII -> i | 3/4 | 144 | 93 BPM | 26.7s | D Minor | **T11** (Cantus Firmus Legatissimo (Sacred Polyphony)) | **S02** (First-Inversion Bass) | **C08** (Anacrusis Loop Bridge) |
| 207 | Loop_207_Em_Lamento_T04_S07_C07 | **Lamento** | Lamento_Chromaticum: i -> VII -> VI -> V | 4/4 | 128 | 46 BPM | 45.2s | E Minor | **T04** (Tirata di Note (Cascades)) | **S07** (Ostinato Pulse First) | **C07** (Plagal Amen Echo) |
| 208 | Loop_208_Fsm_Ciaccona_T09_S04_C06 | **Ciaccona** | Vitali_Passacaglia: i -> iv6 -> V -> i | 3/4 | 144 | 65 BPM | 36.7s | F# Minor | **T09** (Accordo Arpeggiato (Grandioso)) | **S04** (Imitative Tenor Entry) | **C06** (Tierce-Free Open Fifth) |
| 209 | Loop_209_Gm_Toccata_T02_S01_C06 | **Toccata** | Stylus_Phantasticus: i -> iv -> VII -> III | 4/4 | 128 | 83 BPM | 26.6s | G Minor | **T02** (Tasto Solo (Pedal Drone)) | **S01** (Solo Melodic Pickup) | **C06** (Tierce-Free Open Fifth) |
| 210 | Loop_210_Cm_Sarabande_T07_S06_C05 | **Sarabande** | Sarabande_Nobiles: i -> i -> iv -> VII | 3/4 | 144 | 50 BPM | 46.7s | C Minor | **T07** (Campanella (Bell Chime)) | **S06** (Subdominant Opening) | **C05** (Phrygian Cadence Descent) |

---

## Том 08: Собрание 8 | Инструмент: Chamber Piano (Yamaha C5)

| # | ID Файла | Форма | Прогрессия / Граунд | Метр | Шаги | Темп | Длит. | Тональность | Стиль игры (T) | Старт (S) | Каданс (C) |
|---|----------|-------|---------------------|------|------|------|-------|-------------|----------------|-----------|------------|
| 211 | Loop_211_Dm_Canzona_T12_S03_C04 | **Canzona** | Canzona_Francese: i -> iv -> V -> i | 4/4 | 128 | 88 BPM | 25.3s | D Minor | **T12** (Arpeggio Spezzato (Broken Virtuoso Arpeggio)) | **S03** (Dominant Tension Opening) | **C04** (Solo Melodic Echo / Fade) |
| 212 | Loop_212_Em_Siciliana_T05_S08_C03 | **Siciliana** | Siciliana_Pastorale: i -> iv -> ii_dim -> V | 6/8 | 144 | 53 BPM | 44.3s | E Minor | **T05** (Suspiratio (Weeping Sighs)) | **S08** (Dotted Rhetorical Question) | **C03** (Deceptive Resolution to VI) |
| 213 | Loop_213_Fsm_La_Folia_T10_S05_C02 | **La_Folia** | Folia_Antica: i -> V -> i -> VII | 3/4 | 96 | 66 BPM | 25.3s | F# Minor | **T10** (Groppo & Trillo (Ornamental Cadences)) | **S05** (Silent Downbeat) | **C02** (Half-Cadence Open Question) |
| 214 | Loop_214_Am_Ricercar_T03_S02_C01 | **Ricercar** | Ricercar_Cromatico: i -> v -> i -> iv | 4/4 | 128 | 58 BPM | 36.6s | A Minor | **T03** (Chiaroscuro (Dynamic Echo)) | **S02** (First-Inversion Bass) | **C01** (Picardy Cadence & Octave Anchor) |
| 215 | Loop_215_Bm_La_Monica_T08_S07_C08 | **La_Monica** | Monica_Tradizionale: i -> VII -> III -> VII | 4/4 | 128 | 67 BPM | 32.2s | B Minor | **T08** (Staccato Portato (Walking Bass)) | **S07** (Ostinato Pulse First) | **C08** (Anacrusis Loop Bridge) |
| 216 | Loop_216_D_Dor_Spagnoletta_T01_S04_C07 | **Spagnoletta** | Spagnoletta_Antica: i -> iv -> VII -> III | 4/4 | 128 | 74 BPM | 29.4s | D Dorian Minor | **T01** (Style Brisé (Lute Flow)) | **S04** (Imitative Tenor Entry) | **C07** (Plagal Amen Echo) |
| 217 | Loop_217_Em_Pavane_T07_S02_C06 | **Pavane** | Passamezzo_Antico: i -> VII -> i -> V | 4/4 | 128 | 57 BPM | 37.2s | E Minor | **T07** (Campanella (Bell Chime)) | **S02** (First-Inversion Bass) | **C06** (Tierce-Free Open Fifth) |
| 218 | Loop_218_Fsm_Galliard_T12_S07_C05 | **Galliard** | Galliard_Hemiola: i -> III -> VII -> i | 3/4 | 144 | 95 BPM | 26.2s | F# Minor | **T12** (Arpeggio Spezzato (Broken Virtuoso Arpeggio)) | **S07** (Ostinato Pulse First) | **C05** (Phrygian Cadence Descent) |
| 219 | Loop_219_Am_Lamento_T05_S04_C04 | **Lamento** | Lamento_d_Arianna: i -> iv -> V -> i | 4/4 | 128 | 46 BPM | 45.2s | A Minor | **T05** (Suspiratio (Weeping Sighs)) | **S04** (Imitative Tenor Entry) | **C04** (Solo Melodic Echo / Fade) |
| 220 | Loop_220_Bm_Ciaccona_T10_S01_C03 | **Ciaccona** | Romanesca_Ground: III -> VII -> i -> V | 3/4 | 144 | 70 BPM | 34.4s | B Minor | **T10** (Groppo & Trillo (Ornamental Cadences)) | **S01** (Solo Melodic Pickup) | **C03** (Deceptive Resolution to VI) |
| 221 | Loop_221_D_Dor_Toccata_T03_S06_C02 | **Toccata** | Stylus_Phantasticus: i -> iv -> VII -> III | 4/4 | 128 | 85 BPM | 26.1s | D Dorian Minor | **T03** (Chiaroscuro (Dynamic Echo)) | **S06** (Subdominant Opening) | **C02** (Half-Cadence Open Question) |
| 222 | Loop_222_Gm_Sarabande_T08_S03_C01 | **Sarabande** | Sarabande_Nobiles: i -> i -> iv -> VII | 3/4 | 144 | 50 BPM | 46.7s | G Minor | **T08** (Staccato Portato (Walking Bass)) | **S03** (Dominant Tension Opening) | **C01** (Picardy Cadence & Octave Anchor) |
| 223 | Loop_223_Cm_Canzona_T01_S08_C08 | **Canzona** | Canzona_di_Galli: i -> V -> VI -> III | 4/4 | 128 | 80 BPM | 27.5s | C Minor | **T01** (Style Brisé (Lute Flow)) | **S08** (Dotted Rhetorical Question) | **C08** (Anacrusis Loop Bridge) |
| 224 | Loop_224_Dm_Siciliana_T06_S05_C07 | **Siciliana** | Barcarola: i -> v -> i -> iv | 6/8 | 144 | 57 BPM | 41.4s | D Minor | **T06** (Stretto (Polyphonic Canon)) | **S05** (Silent Downbeat) | **C07** (Plagal Amen Echo) |
| 225 | Loop_225_Bm_La_Folia_T11_S02_C07 | **La_Folia** | Folia_Seconda: III -> VII -> i -> V | 3/4 | 96 | 67 BPM | 25.0s | B Minor | **T11** (Cantus Firmus Legatissimo (Sacred Polyphony)) | **S02** (First-Inversion Bass) | **C07** (Plagal Amen Echo) |
| 226 | Loop_226_D_Dor_Ricercar_T04_S07_C06 | **Ricercar** | Ricercar_Antico: i -> i -> iv -> V | 4/4 | 128 | 55 BPM | 38.4s | D Dorian Minor | **T04** (Tirata di Note (Cascades)) | **S07** (Ostinato Pulse First) | **C06** (Tierce-Free Open Fifth) |
| 227 | Loop_227_Gm_La_Monica_T09_S04_C05 | **La_Monica** | Monica_Variata: i -> iv -> VII -> III | 4/4 | 128 | 68 BPM | 31.7s | G Minor | **T09** (Accordo Arpeggiato (Grandioso)) | **S04** (Imitative Tenor Entry) | **C05** (Phrygian Cadence Descent) |
| 228 | Loop_228_Cm_Spagnoletta_T02_S01_C04 | **Spagnoletta** | Spagnoletta_Saltata: i -> VII -> VI -> V | 4/4 | 128 | 75 BPM | 29.1s | C Minor | **T02** (Tasto Solo (Pedal Drone)) | **S01** (Solo Melodic Pickup) | **C04** (Solo Melodic Echo / Fade) |
| 229 | Loop_229_Dm_Pavane_T08_S06_C03 | **Pavane** | Ploravit: i -> v -> VI -> III | 4/4 | 128 | 54 BPM | 39.1s | D Minor | **T08** (Staccato Portato (Walking Bass)) | **S06** (Subdominant Opening) | **C03** (Deceptive Resolution to VI) |
| 230 | Loop_230_Em_Galliard_T01_S03_C02 | **Galliard** | Cinque_Pas: i -> VII -> III -> VII | 3/4 | 144 | 94 BPM | 26.5s | E Minor | **T01** (Style Brisé (Lute Flow)) | **S03** (Dominant Tension Opening) | **C02** (Half-Cadence Open Question) |
| 231 | Loop_231_Fsm_Lamento_T06_S08_C01 | **Lamento** | Lamento_Chromaticum: i -> VII -> VI -> V | 4/4 | 128 | 48 BPM | 43.5s | F# Minor | **T06** (Stretto (Polyphonic Canon)) | **S08** (Dotted Rhetorical Question) | **C01** (Picardy Cadence & Octave Anchor) |
| 232 | Loop_232_Am_Ciaccona_T11_S05_C08 | **Ciaccona** | Ciaccona_di_Paradiso: i -> VII -> VI -> V | 3/4 | 144 | 72 BPM | 33.5s | A Minor | **T11** (Cantus Firmus Legatissimo (Sacred Polyphony)) | **S05** (Silent Downbeat) | **C08** (Anacrusis Loop Bridge) |
| 233 | Loop_233_Cm_Toccata_T04_S02_C07 | **Toccata** | Elevazione: i -> i -> iv6 -> V | 4/4 | 128 | 84 BPM | 26.4s | C Minor | **T04** (Tirata di Note (Cascades)) | **S02** (First-Inversion Bass) | **C07** (Plagal Amen Echo) |
| 234 | Loop_234_Dm_Sarabande_T09_S07_C06 | **Sarabande** | Sarabande_Grave: i -> V -> i -> iv | 3/4 | 144 | 52 BPM | 45.0s | D Minor | **T09** (Accordo Arpeggiato (Grandioso)) | **S07** (Ostinato Pulse First) | **C06** (Tierce-Free Open Fifth) |
| 235 | Loop_235_Em_Canzona_T02_S04_C05 | **Canzona** | Canzona_Francese: i -> iv -> V -> i | 4/4 | 128 | 87 BPM | 25.6s | E Minor | **T02** (Tasto Solo (Pedal Drone)) | **S04** (Imitative Tenor Entry) | **C05** (Phrygian Cadence Descent) |
| 236 | Loop_236_Fsm_Siciliana_T07_S01_C04 | **Siciliana** | Siciliana_Pastorale: i -> iv -> ii_dim -> V | 6/8 | 144 | 54 BPM | 43.5s | F# Minor | **T07** (Campanella (Bell Chime)) | **S01** (Solo Melodic Pickup) | **C04** (Solo Melodic Echo / Fade) |
| 237 | Loop_237_Am_La_Folia_T12_S06_C03 | **La_Folia** | Folia_Antica: i -> V -> i -> VII | 3/4 | 96 | 68 BPM | 24.7s | A Minor | **T12** (Arpeggio Spezzato (Broken Virtuoso Arpeggio)) | **S06** (Subdominant Opening) | **C03** (Deceptive Resolution to VI) |
| 238 | Loop_238_Bm_Ricercar_T05_S03_C02 | **Ricercar** | Ricercar_Cromatico: i -> v -> i -> iv | 4/4 | 128 | 59 BPM | 36.0s | B Minor | **T05** (Suspiratio (Weeping Sighs)) | **S03** (Dominant Tension Opening) | **C02** (Half-Cadence Open Question) |
| 239 | Loop_239_D_Dor_La_Monica_T10_S08_C01 | **La_Monica** | Monica_Tradizionale: i -> VII -> III -> VII | 4/4 | 128 | 69 BPM | 31.3s | D Dorian Minor | **T10** (Groppo & Trillo (Ornamental Cadences)) | **S08** (Dotted Rhetorical Question) | **C01** (Picardy Cadence & Octave Anchor) |
| 240 | Loop_240_Gm_Spagnoletta_T03_S05_C08 | **Spagnoletta** | Spagnoletta_Antica: i -> iv -> VII -> III | 4/4 | 128 | 76 BPM | 28.8s | G Minor | **T03** (Chiaroscuro (Dynamic Echo)) | **S05** (Silent Downbeat) | **C08** (Anacrusis Loop Bridge) |

---

## Том 09: Собрание 9 | Инструмент: Chamber Piano (Yamaha C5)

| # | ID Файла | Форма | Прогрессия / Граунд | Метр | Шаги | Темп | Длит. | Тональность | Стиль игры (T) | Старт (S) | Каданс (C) |
|---|----------|-------|---------------------|------|------|------|-------|-------------|----------------|-----------|------------|
| 241 | Loop_241_Fsm_Pavane_T09_S03_C08 | **Pavane** | Lachrimae: i -> iv -> V -> i | 4/4 | 128 | 54 BPM | 39.1s | F# Minor | **T09** (Accordo Arpeggiato (Grandioso)) | **S03** (Dominant Tension Opening) | **C08** (Anacrusis Loop Bridge) |
| 242 | Loop_242_Am_Galliard_T02_S08_C07 | **Galliard** | Cinque_Pas: i -> VII -> III -> VII | 3/4 | 144 | 96 BPM | 26.0s | A Minor | **T02** (Tasto Solo (Pedal Drone)) | **S08** (Dotted Rhetorical Question) | **C07** (Plagal Amen Echo) |
| 243 | Loop_243_Bm_Lamento_T07_S05_C06 | **Lamento** | Lamento_d_Arianna: i -> iv -> V -> i | 4/4 | 128 | 48 BPM | 43.5s | B Minor | **T07** (Campanella (Bell Chime)) | **S05** (Silent Downbeat) | **C06** (Tierce-Free Open Fifth) |
| 244 | Loop_244_D_Dor_Ciaccona_T12_S02_C05 | **Ciaccona** | Descending_Tetrachord: i -> v6 -> iv6 -> V | 3/4 | 144 | 64 BPM | 37.2s | D Dorian Minor | **T12** (Arpeggio Spezzato (Broken Virtuoso Arpeggio)) | **S02** (First-Inversion Bass) | **C05** (Phrygian Cadence Descent) |
| 245 | Loop_245_Gm_Toccata_T05_S07_C04 | **Toccata** | Elevazione: i -> i -> iv6 -> V | 4/4 | 128 | 86 BPM | 25.8s | G Minor | **T05** (Suspiratio (Weeping Sighs)) | **S07** (Ostinato Pulse First) | **C04** (Solo Melodic Echo / Fade) |
| 246 | Loop_246_Cm_Sarabande_T10_S04_C03 | **Sarabande** | Sarabande_Grave: i -> V -> i -> iv | 3/4 | 144 | 52 BPM | 45.0s | C Minor | **T10** (Groppo & Trillo (Ornamental Cadences)) | **S04** (Imitative Tenor Entry) | **C03** (Deceptive Resolution to VI) |
| 247 | Loop_247_Dm_Canzona_T03_S01_C02 | **Canzona** | Canzona_Francese: i -> iv -> V -> i | 4/4 | 128 | 82 BPM | 26.9s | D Minor | **T03** (Chiaroscuro (Dynamic Echo)) | **S01** (Solo Melodic Pickup) | **C02** (Half-Cadence Open Question) |
| 248 | Loop_248_Em_Siciliana_T08_S06_C01 | **Siciliana** | Siciliana_Pastorale: i -> iv -> ii_dim -> V | 6/8 | 144 | 54 BPM | 43.5s | E Minor | **T08** (Staccato Portato (Walking Bass)) | **S06** (Subdominant Opening) | **C01** (Picardy Cadence & Octave Anchor) |
| 249 | Loop_249_D_Dor_La_Folia_T01_S03_C08 | **La_Folia** | Folia_Antica: i -> V -> i -> VII | 3/4 | 96 | 72 BPM | 23.5s | D Dorian Minor | **T01** (Style Brisé (Lute Flow)) | **S03** (Dominant Tension Opening) | **C08** (Anacrusis Loop Bridge) |
| 250 | Loop_250_Gm_Ricercar_T06_S08_C07 | **Ricercar** | Ricercar_Cromatico: i -> v -> i -> iv | 4/4 | 128 | 59 BPM | 36.0s | G Minor | **T06** (Stretto (Polyphonic Canon)) | **S08** (Dotted Rhetorical Question) | **C07** (Plagal Amen Echo) |
| 251 | Loop_251_Cm_La_Monica_T11_S05_C06 | **La_Monica** | Monica_Tradizionale: i -> VII -> III -> VII | 4/4 | 128 | 73 BPM | 29.8s | C Minor | **T11** (Cantus Firmus Legatissimo (Sacred Polyphony)) | **S05** (Silent Downbeat) | **C06** (Tierce-Free Open Fifth) |
| 252 | Loop_252_Dm_Spagnoletta_T04_S02_C05 | **Spagnoletta** | Spagnoletta_Antica: i -> iv -> VII -> III | 4/4 | 128 | 69 BPM | 31.3s | D Minor | **T04** (Tirata di Note (Cascades)) | **S02** (First-Inversion Bass) | **C05** (Phrygian Cadence Descent) |
| 253 | Loop_253_Em_Pavane_T10_S07_C04 | **Pavane** | Passamezzo_Antico: i -> VII -> i -> V | 4/4 | 128 | 58 BPM | 36.6s | E Minor | **T10** (Groppo & Trillo (Ornamental Cadences)) | **S07** (Ostinato Pulse First) | **C04** (Solo Melodic Echo / Fade) |
| 254 | Loop_254_Fsm_Galliard_T03_S04_C03 | **Galliard** | Galliard_Hemiola: i -> III -> VII -> i | 3/4 | 144 | 95 BPM | 26.2s | F# Minor | **T03** (Chiaroscuro (Dynamic Echo)) | **S04** (Imitative Tenor Entry) | **C03** (Deceptive Resolution to VI) |
| 255 | Loop_255_Am_Lamento_T08_S01_C02 | **Lamento** | Lamento_Chromaticum: i -> VII -> VI -> V | 4/4 | 128 | 50 BPM | 41.9s | A Minor | **T08** (Staccato Portato (Walking Bass)) | **S01** (Solo Melodic Pickup) | **C02** (Half-Cadence Open Question) |
| 256 | Loop_256_Bm_Ciaccona_T01_S06_C01 | **Ciaccona** | Romanesca_Ground: III -> VII -> i -> V | 3/4 | 144 | 66 BPM | 36.2s | B Minor | **T01** (Style Brisé (Lute Flow)) | **S06** (Subdominant Opening) | **C01** (Picardy Cadence & Octave Anchor) |
| 257 | Loop_257_Dm_Toccata_T06_S03_C01 | **Toccata** | Stylus_Phantasticus: i -> iv -> VII -> III | 4/4 | 128 | 85 BPM | 26.1s | D Minor | **T06** (Stretto (Polyphonic Canon)) | **S03** (Dominant Tension Opening) | **C01** (Picardy Cadence & Octave Anchor) |
| 258 | Loop_258_Em_Sarabande_T11_S08_C08 | **Sarabande** | Sarabande_Nobiles: i -> i -> iv -> VII | 3/4 | 144 | 54 BPM | 43.5s | E Minor | **T11** (Cantus Firmus Legatissimo (Sacred Polyphony)) | **S08** (Dotted Rhetorical Question) | **C08** (Anacrusis Loop Bridge) |
| 259 | Loop_259_Fsm_Canzona_T04_S05_C07 | **Canzona** | Canzona_di_Galli: i -> V -> VI -> III | 4/4 | 128 | 89 BPM | 25.1s | F# Minor | **T04** (Tirata di Note (Cascades)) | **S05** (Silent Downbeat) | **C07** (Plagal Amen Echo) |
| 260 | Loop_260_Am_Siciliana_T09_S02_C06 | **Siciliana** | Barcarola: i -> v -> i -> iv | 6/8 | 144 | 58 BPM | 40.7s | A Minor | **T09** (Accordo Arpeggiato (Grandioso)) | **S02** (First-Inversion Bass) | **C06** (Tierce-Free Open Fifth) |
| 261 | Loop_261_Bm_La_Folia_T02_S07_C05 | **La_Folia** | Folia_Seconda: III -> VII -> i -> V | 3/4 | 96 | 62 BPM | 26.7s | B Minor | **T02** (Tasto Solo (Pedal Drone)) | **S07** (Ostinato Pulse First) | **C05** (Phrygian Cadence Descent) |
| 262 | Loop_262_D_Dor_Ricercar_T07_S04_C04 | **Ricercar** | Ricercar_Antico: i -> i -> iv -> V | 4/4 | 128 | 56 BPM | 37.8s | D Dorian Minor | **T07** (Campanella (Bell Chime)) | **S04** (Imitative Tenor Entry) | **C04** (Solo Melodic Echo / Fade) |
| 263 | Loop_263_Gm_La_Monica_T12_S01_C03 | **La_Monica** | Monica_Variata: i -> iv -> VII -> III | 4/4 | 128 | 74 BPM | 29.4s | G Minor | **T12** (Arpeggio Spezzato (Broken Virtuoso Arpeggio)) | **S01** (Solo Melodic Pickup) | **C03** (Deceptive Resolution to VI) |
| 264 | Loop_264_Cm_Spagnoletta_T05_S06_C02 | **Spagnoletta** | Spagnoletta_Saltata: i -> VII -> VI -> V | 4/4 | 128 | 70 BPM | 30.9s | C Minor | **T05** (Suspiratio (Weeping Sighs)) | **S06** (Subdominant Opening) | **C02** (Half-Cadence Open Question) |
| 265 | Loop_265_Am_Pavane_T11_S04_C01 | **Pavane** | Ploravit: i -> v -> VI -> III | 4/4 | 128 | 55 BPM | 38.4s | A Minor | **T11** (Cantus Firmus Legatissimo (Sacred Polyphony)) | **S04** (Imitative Tenor Entry) | **C01** (Picardy Cadence & Octave Anchor) |
| 266 | Loop_266_Bm_Galliard_T04_S01_C08 | **Galliard** | Cinque_Pas: i -> VII -> III -> VII | 3/4 | 144 | 94 BPM | 26.5s | B Minor | **T04** (Tirata di Note (Cascades)) | **S01** (Solo Melodic Pickup) | **C08** (Anacrusis Loop Bridge) |
| 267 | Loop_267_D_Dor_Lamento_T09_S06_C07 | **Lamento** | Passus_Duriusculus: i -> V6 -> i6 -> iv6 | 4/4 | 128 | 47 BPM | 44.4s | D Dorian Minor | **T09** (Accordo Arpeggiato (Grandioso)) | **S06** (Subdominant Opening) | **C07** (Plagal Amen Echo) |
| 268 | Loop_268_Gm_Ciaccona_T02_S03_C06 | **Ciaccona** | Ciaccona_di_Paradiso: i -> VII -> VI -> V | 3/4 | 144 | 68 BPM | 35.3s | G Minor | **T02** (Tasto Solo (Pedal Drone)) | **S03** (Dominant Tension Opening) | **C06** (Tierce-Free Open Fifth) |
| 269 | Loop_269_Cm_Toccata_T07_S08_C05 | **Toccata** | Elevazione: i -> i -> iv6 -> V | 4/4 | 128 | 84 BPM | 26.4s | C Minor | **T07** (Campanella (Bell Chime)) | **S08** (Dotted Rhetorical Question) | **C05** (Phrygian Cadence Descent) |
| 270 | Loop_270_Dm_Sarabande_T12_S05_C04 | **Sarabande** | Sarabande_Grave: i -> V -> i -> iv | 3/4 | 144 | 51 BPM | 45.9s | D Minor | **T12** (Arpeggio Spezzato (Broken Virtuoso Arpeggio)) | **S05** (Silent Downbeat) | **C04** (Solo Melodic Echo / Fade) |

---

## Том 10: Собрание 10 | Инструмент: Chamber Piano (Yamaha C5)

| # | ID Файла | Форма | Прогрессия / Граунд | Метр | Шаги | Темп | Длит. | Тональность | Стиль игры (T) | Старт (S) | Каданс (C) |
|---|----------|-------|---------------------|------|------|------|-------|-------------|----------------|-----------|------------|
| 271 | Loop_271_Em_Canzona_T05_S02_C03 | **Canzona** | Canzona_di_Galli: i -> V -> VI -> III | 4/4 | 128 | 84 BPM | 26.4s | E Minor | **T05** (Suspiratio (Weeping Sighs)) | **S02** (First-Inversion Bass) | **C03** (Deceptive Resolution to VI) |
| 272 | Loop_272_Fsm_Siciliana_T10_S07_C02 | **Siciliana** | Barcarola: i -> v -> i -> iv | 6/8 | 144 | 58 BPM | 40.7s | F# Minor | **T10** (Groppo & Trillo (Ornamental Cadences)) | **S07** (Ostinato Pulse First) | **C02** (Half-Cadence Open Question) |
| 273 | Loop_273_Gm_La_Folia_T03_S04_C02 | **La_Folia** | Folia_Seconda: III -> VII -> i -> V | 3/4 | 96 | 66 BPM | 25.3s | G Minor | **T03** (Chiaroscuro (Dynamic Echo)) | **S04** (Imitative Tenor Entry) | **C02** (Half-Cadence Open Question) |
| 274 | Loop_274_Cm_Ricercar_T08_S01_C01 | **Ricercar** | Ricercar_Antico: i -> i -> iv -> V | 4/4 | 128 | 56 BPM | 37.8s | C Minor | **T08** (Staccato Portato (Walking Bass)) | **S01** (Solo Melodic Pickup) | **C01** (Picardy Cadence & Octave Anchor) |
| 275 | Loop_275_Dm_La_Monica_T01_S06_C08 | **La_Monica** | Monica_Variata: i -> iv -> VII -> III | 4/4 | 128 | 67 BPM | 32.2s | D Minor | **T01** (Style Brisé (Lute Flow)) | **S06** (Subdominant Opening) | **C08** (Anacrusis Loop Bridge) |
| 276 | Loop_276_Em_Spagnoletta_T06_S03_C07 | **Spagnoletta** | Spagnoletta_Saltata: i -> VII -> VI -> V | 4/4 | 128 | 74 BPM | 29.4s | E Minor | **T06** (Stretto (Polyphonic Canon)) | **S03** (Dominant Tension Opening) | **C07** (Plagal Amen Echo) |
| 277 | Loop_277_Fsm_Pavane_T12_S08_C06 | **Pavane** | Lachrimae: i -> iv -> V -> i | 4/4 | 128 | 55 BPM | 38.4s | F# Minor | **T12** (Arpeggio Spezzato (Broken Virtuoso Arpeggio)) | **S08** (Dotted Rhetorical Question) | **C06** (Tierce-Free Open Fifth) |
| 278 | Loop_278_Am_Galliard_T05_S05_C05 | **Galliard** | Cinque_Pas: i -> VII -> III -> VII | 3/4 | 144 | 96 BPM | 26.0s | A Minor | **T05** (Suspiratio (Weeping Sighs)) | **S05** (Silent Downbeat) | **C05** (Phrygian Cadence Descent) |
| 279 | Loop_279_Bm_Lamento_T10_S02_C04 | **Lamento** | Lamento_Chromaticum: i -> VII -> VI -> V | 4/4 | 128 | 47 BPM | 44.4s | B Minor | **T10** (Groppo & Trillo (Ornamental Cadences)) | **S02** (First-Inversion Bass) | **C04** (Solo Melodic Echo / Fade) |
| 280 | Loop_280_D_Dor_Ciaccona_T03_S07_C03 | **Ciaccona** | Descending_Tetrachord: i -> v6 -> iv6 -> V | 3/4 | 144 | 60 BPM | 39.5s | D Dorian Minor | **T03** (Chiaroscuro (Dynamic Echo)) | **S07** (Ostinato Pulse First) | **C03** (Deceptive Resolution to VI) |
| 281 | Loop_281_Em_Toccata_T08_S04_C02 | **Toccata** | Elevazione: i -> i -> iv6 -> V | 4/4 | 128 | 86 BPM | 25.8s | E Minor | **T08** (Staccato Portato (Walking Bass)) | **S04** (Imitative Tenor Entry) | **C02** (Half-Cadence Open Question) |
| 282 | Loop_282_Fsm_Sarabande_T01_S01_C01 | **Sarabande** | Sarabande_Grave: i -> V -> i -> iv | 3/4 | 144 | 51 BPM | 45.9s | F# Minor | **T01** (Style Brisé (Lute Flow)) | **S01** (Solo Melodic Pickup) | **C01** (Picardy Cadence & Octave Anchor) |
| 283 | Loop_283_Am_Canzona_T06_S06_C08 | **Canzona** | Canzona_Francese: i -> iv -> V -> i | 4/4 | 128 | 91 BPM | 24.6s | A Minor | **T06** (Stretto (Polyphonic Canon)) | **S06** (Subdominant Opening) | **C08** (Anacrusis Loop Bridge) |
| 284 | Loop_284_Bm_Siciliana_T11_S03_C07 | **Siciliana** | Siciliana_Pastorale: i -> iv -> ii_dim -> V | 6/8 | 144 | 55 BPM | 42.8s | B Minor | **T11** (Cantus Firmus Legatissimo (Sacred Polyphony)) | **S03** (Dominant Tension Opening) | **C07** (Plagal Amen Echo) |
| 285 | Loop_285_D_Dor_La_Folia_T04_S08_C06 | **La_Folia** | Folia_Antica: i -> V -> i -> VII | 3/4 | 96 | 67 BPM | 25.0s | D Dorian Minor | **T04** (Tirata di Note (Cascades)) | **S08** (Dotted Rhetorical Question) | **C06** (Tierce-Free Open Fifth) |
| 286 | Loop_286_Gm_Ricercar_T09_S05_C05 | **Ricercar** | Ricercar_Cromatico: i -> v -> i -> iv | 4/4 | 128 | 60 BPM | 35.5s | G Minor | **T09** (Accordo Arpeggiato (Grandioso)) | **S05** (Silent Downbeat) | **C05** (Phrygian Cadence Descent) |
| 287 | Loop_287_Cm_La_Monica_T02_S02_C04 | **La_Monica** | Monica_Tradizionale: i -> VII -> III -> VII | 4/4 | 128 | 68 BPM | 31.7s | C Minor | **T02** (Tasto Solo (Pedal Drone)) | **S02** (First-Inversion Bass) | **C04** (Solo Melodic Echo / Fade) |
| 288 | Loop_288_Dm_Spagnoletta_T07_S07_C03 | **Spagnoletta** | Spagnoletta_Antica: i -> iv -> VII -> III | 4/4 | 128 | 75 BPM | 29.1s | D Minor | **T07** (Campanella (Bell Chime)) | **S07** (Ostinato Pulse First) | **C03** (Deceptive Resolution to VI) |
| 289 | Loop_289_Bm_Pavane_T01_S05_C03 | **Pavane** | Passamezzo_Antico: i -> VII -> i -> V | 4/4 | 128 | 52 BPM | 40.4s | B Minor | **T01** (Style Brisé (Lute Flow)) | **S05** (Silent Downbeat) | **C03** (Deceptive Resolution to VI) |
| 290 | Loop_290_D_Dor_Galliard_T06_S02_C02 | **Galliard** | Galliard_Hemiola: i -> III -> VII -> i | 3/4 | 144 | 95 BPM | 26.2s | D Dorian Minor | **T06** (Stretto (Polyphonic Canon)) | **S02** (First-Inversion Bass) | **C02** (Half-Cadence Open Question) |
| 291 | Loop_291_Gm_Lamento_T11_S07_C01 | **Lamento** | Passus_Duriusculus: i -> V6 -> i6 -> iv6 | 4/4 | 128 | 49 BPM | 42.7s | G Minor | **T11** (Cantus Firmus Legatissimo (Sacred Polyphony)) | **S07** (Ostinato Pulse First) | **C01** (Picardy Cadence & Octave Anchor) |
| 292 | Loop_292_Cm_Ciaccona_T04_S04_C08 | **Ciaccona** | Romanesca_Ground: III -> VII -> i -> V | 3/4 | 144 | 62 BPM | 38.3s | C Minor | **T04** (Tirata di Note (Cascades)) | **S04** (Imitative Tenor Entry) | **C08** (Anacrusis Loop Bridge) |
| 293 | Loop_293_Dm_Toccata_T09_S01_C07 | **Toccata** | Stylus_Phantasticus: i -> iv -> VII -> III | 4/4 | 128 | 85 BPM | 26.1s | D Minor | **T09** (Accordo Arpeggiato (Grandioso)) | **S01** (Solo Melodic Pickup) | **C07** (Plagal Amen Echo) |
| 294 | Loop_294_Em_Sarabande_T02_S06_C06 | **Sarabande** | Sarabande_Nobiles: i -> i -> iv -> VII | 3/4 | 144 | 53 BPM | 44.3s | E Minor | **T02** (Tasto Solo (Pedal Drone)) | **S06** (Subdominant Opening) | **C06** (Tierce-Free Open Fifth) |
| 295 | Loop_295_Fsm_Canzona_T07_S03_C05 | **Canzona** | Canzona_di_Galli: i -> V -> VI -> III | 4/4 | 128 | 83 BPM | 26.6s | F# Minor | **T07** (Campanella (Bell Chime)) | **S03** (Dominant Tension Opening) | **C05** (Phrygian Cadence Descent) |
| 296 | Loop_296_Am_Siciliana_T12_S08_C04 | **Siciliana** | Barcarola: i -> v -> i -> iv | 6/8 | 144 | 52 BPM | 45.0s | A Minor | **T12** (Arpeggio Spezzato (Broken Virtuoso Arpeggio)) | **S08** (Dotted Rhetorical Question) | **C04** (Solo Melodic Echo / Fade) |
| 297 | Loop_297_Cm_La_Folia_T05_S05_C03 | **La_Folia** | Folia_Seconda: III -> VII -> i -> V | 3/4 | 96 | 68 BPM | 24.7s | C Minor | **T05** (Suspiratio (Weeping Sighs)) | **S05** (Silent Downbeat) | **C03** (Deceptive Resolution to VI) |
| 298 | Loop_298_Dm_Ricercar_T10_S02_C02 | **Ricercar** | Ricercar_Antico: i -> i -> iv -> V | 4/4 | 128 | 57 BPM | 37.2s | D Minor | **T10** (Groppo & Trillo (Ornamental Cadences)) | **S02** (First-Inversion Bass) | **C02** (Half-Cadence Open Question) |
| 299 | Loop_299_Em_La_Monica_T03_S07_C01 | **La_Monica** | Monica_Variata: i -> iv -> VII -> III | 4/4 | 128 | 69 BPM | 31.3s | E Minor | **T03** (Chiaroscuro (Dynamic Echo)) | **S07** (Ostinato Pulse First) | **C01** (Picardy Cadence & Octave Anchor) |
| 300 | Loop_300_Fsm_Spagnoletta_T08_S04_C08 | **Spagnoletta** | Spagnoletta_Saltata: i -> VII -> VI -> V | 4/4 | 128 | 76 BPM | 28.8s | F# Minor | **T08** (Staccato Portato (Walking Bass)) | **S04** (Imitative Tenor Entry) | **C08** (Anacrusis Loop Bridge) |
