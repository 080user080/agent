import google.generativeai as genai
import os
import time

# 1. Налаштування API ключа
# Рекомендується зберігати ключ у змінних оточення
os.environ["GEMINI_API_KEY"] = "AIzaSyAzTmRM6bkqxNyfEdqwve1VupoSxitdFNg" 
genai.configure(api_key=os.environ["GEMINI_API_KEY"])

# 2. Вибір моделі (Flash — найшвидша і має найбільші ліміти для безкоштовного рівня)
model = genai.GenerativeModel('gemini-flash-latest')

# Ваша інструкція та текст (з виправленим закриттям рядка)
prompt = """
|
Перекласти на українську
  # ІНСТРУКЦІЯ З РОЗМІТКИ ТА ОБРОБКИ ТЕКСТУ
  
  ## 1. Загальна мета
  
  Ця інструкція визначає єдині, однозначні правила автоматичної обробки художнього тексту з використанням тегів мовців. Результат має бути однаково коректно інтерпретований будь-якою ШІ-системою (ChatGPT, Gemini тощо) без додаткових пояснень.
  
  Мета обробки:
  
  * уніфікувати структуру тексту;
  * чітко позначити мовця або тип оповіді кожного фрагмента;
  * усунути зайві повтори тегів;
  * виправити пунктуаційні помилки без зміни змісту;
  * не додавати жодних нових смислів, стилістичних прикрас або коментарів.
  
  ---
  
  ## 2. Теги мовців
  
  ### 2.1. Дозволені теги
  
  Дозволено використовувати **виключно** заздалегідь визначений список тегів. Жодні інші теги, варіації, синоніми або довільні позначення **заборонені**.
  
  Формат тегу:
  
  ```
  #gX:
  ```
  
  де `X` — номер мовця або типу оповіді.
  
  Приклад:
  
  ```
  #g1:
  ```
  
  ---
  
  ## 3. Базові правила розмітки
  
  ### 3.1. Початок рядка
  
  * Кожен текстовий блок **обов’язково** починається з тегу.
  * Тег завжди стоїть **на початку рядка**.
  * Після тегу ставиться **один пробіл**, далі текст.
  
  Правильно:
  
  ```
  #g1: Текст...
  ```
  
  Неправильно:
  
  ```
  #g1:Текст...
  #g1 : Текст...
  Текст без тегу
  ```
  
  ---
  
  ### 3.2. Один мовець — один блок
  
  * Якщо **кілька сусідніх рядків** належать **одному й тому самому мовцю** (тобто мають однаковий тег), вони **об’єднуються в один рядок**.
  * Повторення одного й того ж тегу поспіль **заборонене**.
  
  #### Приклад
  
  Вхідний текст:
  
  ```
  #g1: Послушники негайно взялися до справи.
  #g1: Тобіас затримався на п’ятирозмір, приголомшений тим, як швидко став чужим.
  #g1: Лише Мара ще дивилася на нього; зустрівши погляд, вона відвернулася і рушила до мішеней.
  ```
  
  Правильний результат:
  
  ```
  #g1: Послушники негайно взялися до справи. Тобіас затримався на п’ятирозмір, приголомшений тим, як швидко став чужим. Лише Мара ще дивилася на нього; зустрівши погляд, вона відвернулася і рушила до мішеней.
  ```
  
  ---
  ### 3.3. Один мовець — один блок 

  * ** кожний мовець має бути чітко бути виділений своїм тегом**;
  * кожний мовець має говорити тільки свою репліку -- уважно стежити за репліками оповідача
  
  Вхідний текст:
  Неправильно:
  ```
  #g6: Почали. — Він відступив.
  ```
  Правильно:
  ```
  #g6: Почали.
  #g1: Він відступив.
  ```

  ---
  
  ## 4. Пунктуація та орфографія
  
  ### 4.1. Загальне правило
  
  * Якщо в тексті виявлено **пунктуаційні або орфографічні помилки**, їх **потрібно виправити**.
  * Виправлення **не повинні** змінювати зміст, стиль, темп або авторську інтонацію.
  
  ### 4.2. Дозволено
  
  * додавання або вилучення пропущених ком;
  * виправлення неправильних лапок;
  * виправлення очевидних друкарських помилок;
  * корекція дефісів, апострофів, тире відповідно до норм мови.
  
  ### 4.3.  Текстова нормалізація чисел

  * Заміна цифрових позначень повною текстовою формою (числівниками);
  * числівники повинні мати граматично правильну форму у реченнях;

  * **теги #gN: -- забороненно змінювати для перетворення у числівники**.
  
  ---
  
  ## 5. Заборонені дії
  
  ### 5.1. Заборонені слова-посилання
  
  Заборонено використовувати слова та конструкції, що прямо називають акт мовлення, зокрема (але не обмежуючись):
  
  * «сказав»
  * «відповів»
  * «запитав»
  * «промовив»
  * «мовив»
  * будь-які їхні граматичні або синонімічні аналоги.
  
  ### 5.2. Якщо ці слова є в оригінальному тексті
  
  * Вони **мають бути усунені або нейтралізовані** так, щоб **не було прямого посилання на акт мовлення**.
  * Зміст фрази при цьому зберігається максимально близько до оригіналу.
  
  ---
  
  ## 6. Структурні обмеження
  
  * Заборонено додавати пояснення, примітки, коментарі від обробника тексту.
  * Заборонено вставляти службові повідомлення, маркери або мета‑інформацію.
  * Вихідний результат — **лише оброблений текст із тегами**.
  * Вихідний результат — **лише оброблений текст із тегами - *без пропозицій* *без повідомлень* від google без повідомлень від gemini *без запитань* *без зайвих заголовків чи висновків* **.
  
  * Вихідний результат — **лише оброблений текст із тегами - *без пропозицій* *без повідомлень* від google без повідомлень від gemini *без запитань* *без зайвих заголовків чи висновків* **.

  * Відповідь — **тільки оброблений текст із тегами**.

  ---
  
  ## 7. Перевірка на суперечності
  
  Перед фінальним результатом обробки **обов’язково** має бути виконана внутрішня перевірка:
  
  * вхіний текст має бут оброблений від першого до останнього символу;
  * кожен рядок має рівно один тег;
  * однакові теги не повторюються поспіль;
  * жодне правило не суперечить іншому;
  * пунктуація виправлена, але зміст не змінений;
  * не використано заборонені слова та конструкції.
  
  ---
  
  ## 8. Очікуваний результат
  
  Коректний результат:
  
  * структурований;
  * однозначний;
  * машинно читабельний;
  * ** кожний мовець має бути чітко бути виділений  своїм тегом**
  * придатний для TTS, аналізу або подальшої автоматичної обробки;
  * зрозумілий будь-якій сучасній ШІ-моделі без додаткового контексту.

  --- Дозволені теги ---
  Використовувати виключно цей список тегів, без змін, скорочень або вигадування нових:
  #g1: - Оповідач (третя особа, фокус на Тобіаса)
  #g2: - Тобіас Долджане (M, головний герой, Мандрівник-Ходун)
  #g3: - Мара (F, подруга Тобіаса, послушниця-Ладівник)
  #g4: - Канцлер Шаан (M, керівник палацу Віндхоум)
  #g5: - Майстер Оджейд (Вайсан) (M, наставник Тобіаса, Майстер Ходок)
  #g6: - Сафферн (M, майстер зброї)
  #g7: - Вансі Товорл (F, Палацова Зв'язувачка)
  #g8: - Дрое (F, Тіррібін, демон часу)
  #g9: - Белвора (M, магічний демон, має внутрішній монолог)
  #g10: - Делвін (M, послушник, друг Тобіаса)
  #g11: - Нат (M, послушник, старший за Тобіаса)
  #g12: - Вісник (M, службовець канцлера)
  #g13: - Будь-який *тимчасовий персонаж чоловічого роду* який не увійшов до попередніх мовців
  #g14: - Будь-який *тимчасовий персонаж жіночого роду* який не увійшов до попередніх мовців
  
  --- ГЛОСАРІЙ взятий із перекладу ---

  **Переклад:** Мара
  **Коментар:** Головна героїня; Ходун і Ладівник, вихована у Палаці Мандрівників у Віндхоумі.
  
  **Переклад:** Тобіас
  **Коментар:** Головний герой; Ходун, який рятує принцесу Гайнкалде.
  
  **Переклад:** Нава / Софія
  **Коментар:** Немовля-принцеса Гайнкалде; центральна фігура політичного конфлікту.
  
  **Переклад:** Ґілліан Ейнфор
  **Коментар:** Міністерка, пов’язана з Байндером Філтом; зраджує героїв.
  
  **Переклад:** Філт
  **Коментар:** Байндер; майстер золотих магічних приладів.
  
  **Переклад:** Каарті
  **Коментар:** Господиня прихистку в Засічі; допомагає Тобіасу та дитині.
  
  **Переклад:** Ганрід
  **Коментар:** Провидець; має дар передбачення майбутніх гілок.
  
  **Переклад:** Нуала
  **Коментар:** Верховна жриця, що підтримує Елінор і допомагає врятувати дитину.
  
  **Переклад:** Елінор Тіммін
  **Коментар:** Жінка, яка знаходить Тобіаса з немовлям і звертається до Нуали.
  
  **Переклад:** Уджіє
  **Коментар:** Аррокад — морська демонічна істота, з якою Тобіас укладає угоду.
  
  **Переклад:** Орзилі
  **Коментар:** Переслідувач, пов’язаний із Шерайх; убив правителя Гайнкалде.
  
  **Переклад:** Тіло
  **Коментар:** Демон Тіррібін; попереджає Тобіаса.
  
  **Переклад:** Мандрівники
  **Коментар:** Каста людей із часо-просторовими здібностями.
  
  **Переклад:** Ходуни
  **Коментар:** Мандрівники, що здійснюють переміщення в часі.
  
  **Переклад:** Ладівники
  **Коментар:** Мандрівники, здатні переміщуватися на далекі відстані у просторі.
  
  **Переклад:** Перетинники
  **Коментар:** Мандрівники, що проходять крізь тверді об’єкти через апертуру.
  
  **Переклад:** В’язальники
  **Коментар:** Майстри зі створення магічних золотих артефактів.
  
  **Переклад:** Провидці
  **Коментар:** Люди, здатні бачити можливі майбутні варіанти світу.
  
  **Переклад:** Шерайх
  **Коментар:** Ворожа сила/держава, що переслідує героїв.
  
  **Переклад:** Аррокад
  **Коментар:** Морські демонічні істоти, здатні укладати магічні договори.
  
  **Переклад:** Бельвора
  **Коментар:** Крілаті хижі демони з півночі.
  
  **Переклад:** Тіррібін
  **Коментар:** Демони-мисливці, швидкі та смертельно небезпечні.
  
  **Переклад:** Апертура
  **Коментар:** Золотий обруч для створення порталу в твердій поверхні.
  
  **Переклад:** Хронофор
  **Коментар:** Прилад для переміщення в часі, схожий на складний годинник.
  
  **Переклад:** Секстант / Трисекстант
  **Коментар:** Магічні прилади Байндерів, пов’язані зі складними вимірами.
  
  **Переклад:** Міжчасся
  **Коментар:** Простір між часовими точками, доступний Ходунам.
  
  **Переклад:** Провалля
  **Коментар:** Просторовий вимір, через який пересуваються Ладівники.
  
  **Переклад:** Віндхоум
  **Коментар:** Північний острів; осередок Палацу Мандрівників.
  
  **Переклад:** Кільцеві острови
  **Коментар:** Архіпелаг біля Внутрішнього моря.
  
  **Переклад:** Внутрішнє море
  **Коментар:** Центральне море архіпелагу.
  
  **Переклад:** Айянт
  **Коментар:** Місто, до якого прагнуть дістатися герої.
  
  **Переклад:** Засіч
  **Коментар:** Небезпечне ущелинне поселення; притулок вигнанців.
  
  **Переклад:** Гайнкалде
  **Коментар:** Королівство принцеси; центр політичної змови.
  
  **Переклад:** Лабіринт
  **Коментар:** Північне місце походження Мандрівників і Провидців.
  
  **Переклад:** Сестри
  **Коментар:** Група островів поблизу Віндхоуму.
  
  **Переклад:** Кантаад
  **Коментар:** Місце виробництва кораблів Кант.
  
  **Переклад:** Спайркаунт
  **Коментар:** Найменша одиниця часу.
  
  **Переклад:** Дзвінок
  **Коментар:** Одиниця часу, рівна п’ятдесяти спайркаунтам.
  
  **Переклад:** Півколо
  **Коментар:** Період у п’ятнадцять днів.
  
  **Переклад:** П’ятирозмір
  **Коментар:** Коротка пауза, відлік до п’яти.
  
  **Переклад:** Треї
  **Коментар:** Місцева валюта.
  
  **Переклад:** Настій
  **Коментар:** Вибухонебезпечна рідина, яку Мара використовує для диверсій.
  
  --- КІНЕЦЬ ГЛОСАРІЮ ---
  
  --- ТЕКСТ ДЛЯ ВИПРАВЛЕННЯ ---
"""

text_to_process = """
Chapter 1 -- Hooch


Not many flatboats were getting down the Hio these days, not with pioneers aboard, anyway, not with families and tools and furniture and seed and a few shoats to start a pig herd.
It took only a couple of fire arrows and pretty soon some tribe of Reds would have themselves a string of half-charred scalps to sell to the French in Detroit.
But Hooch Palmer had no such trouble.
The Reds all knew the look of his flatboat, stacked high with kegs.
Most of those kegs sloshed with whisky, which was about the only musical sound them Reds understood.
But in the middle of the vast heap of cooperage there was one keg that didn’t slosh.
It was filled with gunpowder, and it had a fuse attached.
How did he use that gunpowder?
They’d be floating along with the current, poling on round a bend, and all of a sudden there’d be a half-dozen canoes filled with painted-up Reds of the Kicky-Poo persuasion.
Or they’d see a fire burning near shore, and some Shaw-Nee devils dancing around with arrows ready to set alight.
For most folks that meant it was time to pray, fight, and die.
Not Hooch, though.
He’d stand right up in the middle of that flatboat, a torch in one hand and the fuse in the other, and shout, “Blow up whisky!
Blow up whisky!”

Well, most Reds didn’t talk much English, but they sure knew what “blow up” and “whisky” meant.
And I instead of arrows flying or canoes overtaking them, pretty soon them canoes passed by him on the far side of the river.
Some Red yelled, “Carthage City!” and Hooch hollered back, “That’s right!” and the canoes just zipped on down the Hio, heading for where that likker would soon be sold.
The poleboys, of course, it was their first trip downriver, and they, didn’t know all that Hooch Palmer knew, so they about filled their trousers first time they saw them Reds with fire arrows.
And when they saw Hooch holding his torch by that fuse, they like to jumped right in the river.
Hooch just laughed and laughed.
“You boys don’t know about Reds and likker,” he said.
“They won’t do nothing that might cause a single drop from these kegs to spill into the Hio.
They’d kill their own mother and not think twice, if she stood between them and a keg, but they won’t touch us as long as I got the gunpowder ready to blow if they lay one hand on me.”

Privately the poleboys might wonder if Hooch really would blow the whole raft, crew and all, but the fact is Hooch would.
He wasn’t much of a thinker, nor did he spend much time brooding about death and the hereafter or such philosophical questions, but this much he had decided: when he died, he supposed he wouldn’t die alone.
He also supposed that if somebody killed him, they’d get no profit from the deed, none at all.
Specially not some half-drunk weak-sister cowardly Red with a scalping knife.
The best secret of all was, Hooch wouldn’t need no torch and he wouldn’t need no fuse, neither.
Why, that fuse didn’t even go right into the gunpowder keg, if the truth be known—Hooch didn’t want a chance of that powder going off by accident.
No, if Hooch ever needed to blow up his flatboat, he could just set down and think about it for a while.
And pretty soon that powder would start to hotten up right smart, and maybe a little smoke would come off it, and then pow!
it goes off.
That’s right.
Old Hooch was a spark.
Oh, there’s some folks says there’s no such thing as a spark, and for proof they say, “Have you ever met a spark, or knowed anybody who did?” but that’s no proof at all.
Cause if you happen to be a spark, you don’t go around telling everybody, do you?
It’s not as if anybody’s hoping to hire your services—it’s too easy to use flint and steel, or even them alchemical matches.
No, the only value there is to being a spark is if you want to start a fire from a distance, and the only time you want to do that is if it’s a bad fire, meant to hurt somebody, burn down a building, blow something up.
And if you hire out that kind of service, you don’t exactly put up a sign that says Spark For Hire.
Worst of it is that if word once gets around that you’re a spark, every little fire gets blamed on you.
Somebody’s boy lights up a pipe out in the bam, and the barn burns down—does that boy ever say, “Yep, Pa, it was me all right.” No sir, that boy says, “Must’ve been some spark set that fire, Pa!” and then they go looking for you, the neighborhood scapegoat.
No, Hooch was no fool.
He didn’t ever tell nobody about how he could get things het up and flaming.
There was another reason Hooch didn’t use his sparking ability too much.
It was a reason so secret that Hooch didn’t rightly know it himself.
Thing was, fire scared him.
Scared him deep.
The way some folks is scared of water, and so they go to sea; and some folks is scared of death, and so they take up gravedigging; and some folks is scared of God, and so they set to preaching.
Well Hooch feared the fire like he feared no other thing, and so he was always drawn to it, with that sick feeling in his stomach; but when it was time for him to lay a fire himself, why, he’d back off, he’d delay, he’d think of reasons why he shouldn’t do it at all.
Hooch had a knack, but he was powerful reluctant to make much use of it.
But he would have done it.
He would have blown up that powder and himself and his poleboys, and all his likker, before he’d let a Red take it by murder.
Hooch might have his bad fear of fire, but he’d overcome it right quick if he got mad enough.
Good thing, then, that the Reds loved likker so much they didn’t want to risk spilling a drop.
No canoe came too close, no arrow whizzed in to thud and twang against a keg, and Hooch and his kegs and casks and firkins and barrels all slipped along the top of the water peaceful as you please, clear to Carthage City, which was Governor Harrison’s high-falutin name for a stockade with a hundred soldiers right smack where the Little My-Ammy River met the Hio.
But Bill Harrison was the kind of man who gave the name first, then worked hard to make the place live up to the name.
And sure enough, there was about fifty chimney fires outside the stockade this time, which meant Carthage City was almost up to being a village.
He could hear them yelling before he hove into view of the wharf—there must be Reds who spent half their life just setting on the riverbank waiting for the likker boat to come in.
And Hooch knew they were specially eager this time, seeing as how some money changed hands back in Fort Dekane, so the other likker dealers got held up this way and that until old Carthage City must be dry as the inside of a bull’s tit.
Now here comes Hooch with his flatboat loaded up heavier than they ever saw, and he’d get a price this time, that’s for sure.
Bill Harrison might be vain as a partridge, taking on airs and calling himself governor when nobody elected him and nobody appointed him but his own self, but he knew his business.
He had those boys of his in smart-looking uniforms, lined up at the wharf just as neat as you please, their muskets loaded and ready to shoot down the first Red who so much as took a step toward the shore.
It was no formality, neither—them Reds looked mighty eager, Hooch could see.
Not jumping up and down like children, of course, but just standing there, just standing and watching, right out in the open, not caring who saw them, half-naked the way they mostly were in summertime.
Standing there all humble, all ready to bow and scrape, to beg and plead, to say, Please Mr.
Hooch one keg for thirty deerskins, oh that would sound sweet, oh indeed it would; Please Mr.
Hooch one tin cup of likker for these ten muskrat hides.
“Whee-haw!” cried Hooch.
The poleboys looked at him like he was crazy, cause they didn’t know, they never saw how these Reds used to look, back before Governor Harrison set up shop here, the way they never deigned to look at a White man, the way you had to crawl into their wicky-ups and choke half to death on smoke and steam and sit there making signs and talking their jub-jub until you got permission to wade.
Used to be the Reds would be standing there with bows and spears, and you’d be scared to death they’d decide your scalp was worth more than your trade goods.
Not anymore.
Now they didn’t have a single weapon among them.
Now their tongues just hung out waiting for likker.
And they’d drink and drink and drink and drink and drink and whee-haw!
They’d drop down dead before they’d ever stop drinking, which was the best thing of all, best thing of all.
Only good Red’s a dead Red, Hooch always said, and the way he and Bill Harrison had things going now, they had them Reds dying of likker at a good clip, and paying for the privilege along the way.
So Hooch was about as happy a man as you ever saw when they tied up at the Carthage City Wharf.
The sergeant even saluted him, if you could believe it!
A far cry from the way the U.S.
Marshalls treated him back in Suskwahenny, acting like he was scum they just scraped off the privy seat.
Out here in this new country, free-spirited men like Hooch were treated most like gentlemen, and that suited Hooch just fine.
Let them pioneers with their tough ugly wives and wiry little brats go hack down trees and cut up the dirt and raise corn and hogs just to live.
Not Hooch.
He’d come in after, after the fields were all nice and neat looking and the houses were all in fine rows on squared-off streets, and then he’d take his money and buy him the biggest house in town, and the banker would step off the sidewalk into the mud to make way for him, and the mayor would call him sir—if he didn’t decide to be mayor himself by then.
This was the message of the sergeant’s salute, telling his future for him, when he stepped ashore.
“We’ll unload here, Mr.
Hooch,” said the sergeant.
“I’ve got a bill of lading,” said Hooch, “so let’s have no privateering by your boys.
Though I’d allow as how there’s probably one keg of good rye whisky that somehow didn’t exactly get counted on here.
"""
# 3. Генерація тексту з таймером
start_time = time.time()  # Початок відліку

response = model.generate_content(prompt + text_to_process)

end_time = time.time()    # Кінець відліку

# Обчислення різниці
execution_time = end_time - start_time

print(response.text)
print("-" * 30)
print(f"Gemini думав : {execution_time:.2f} секунд")
