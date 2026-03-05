from datetime import date, timedelta
from django.core.management.base import BaseCommand
from apps.writings.models import Writing
from apps.tags.models import Tag


class Command(BaseCommand):
    help = "Seed sample writings for development"

    def handle(self, *args, **options):
        if Writing.objects.exists():
            self.stdout.write("Writings already exist, skipping seed.")
            return

        # Ensure tags exist
        tag_reflection, _ = Tag.objects.get_or_create(name="Spiritual Reflection", defaults={"slug": "spiritual-reflection"})
        tag_advice, _ = Tag.objects.get_or_create(name="Advice", defaults={"slug": "advice"})
        tag_motivation, _ = Tag.objects.get_or_create(name="Motivation", defaults={"slug": "motivation"})
        tag_dua, _ = Tag.objects.get_or_create(name="Du'a & Dhikr", defaults={"slug": "dua-dhikr"})
        tag_reminder, _ = Tag.objects.get_or_create(name="Daily Reminder", defaults={"slug": "daily-reminder"})

        writings_data = [
            {
                "title": "The Sweetness of Sabr",
                "body": "Patience is not merely the absence of complaint. It is the deep trust that Allah's plan is unfolding exactly as it should.\n\nThe one who plants seeds of sabr in the garden of the heart will harvest fruits of peace that no worldly comfort can match. Every trial is a conversation between you and your Lord.\n\nWhen the world presses you from every side, remember that diamonds are formed under pressure. Your struggles are not punishments — they are refinements. Allah does not burden a soul beyond what it can bear.\n\nThe Prophet (peace be upon him) said: 'How wonderful is the affair of the believer, for his affairs are all good.' In ease, we are grateful. In hardship, we are patient. And in both, we draw closer to the One who created us.",
                "published_date": date.today(),
                "tags": [tag_reflection],
            },
            {
                "title": "Rise Before the Sun",
                "body": "The hours before Fajr hold a secret that the sleeping world will never know.\n\nIn the stillness of the last third of the night, when the world is quiet and the soul is awake, there is a door open between heaven and earth. Those who rise will find it.\n\nAllah descends to the lowest heaven and asks: 'Is there anyone who calls upon Me, that I may answer him? Is there anyone who asks of Me, that I may give him? Is there anyone who seeks My forgiveness, that I may forgive him?'\n\nDo not let the comfort of your bed steal this gift from you. The tahajjud prayer is the secret weapon of the believer — a time when du'as are answered and hearts are mended.",
                "published_date": date.today() - timedelta(days=7),
                "tags": [tag_motivation],
            },
            {
                "title": "Morning Adhkar: A Shield for Your Day",
                "body": "The Prophet (SAW) never left the morning adhkar. These simple words are a fortress around the believer, a shield against anxiety, a light through darkness.\n\nBegin each day by remembering the One who gave you that day. Say 'Bismillah' before you step out. Recite Ayat al-Kursi for protection. Read the three Quls and blow over yourself.\n\nThese are not mere rituals — they are spiritual armor. The remembrance of Allah brings tranquility to the heart in a way that nothing in this dunya can replicate.\n\n'Verily, in the remembrance of Allah do hearts find rest.' (Quran 13:28)",
                "published_date": date.today() - timedelta(days=14),
                "tags": [tag_dua],
            },
            {
                "title": "Guard Your Tongue, Guard Your Heart",
                "body": "The tongue is small but its consequences are enormous. A single word of backbiting can erase a month of worship. A single word of kindness can plant a tree in Jannah.\n\nThe wise one speaks little and reflects much, for silence is the garden where wisdom grows. Before you speak, ask yourself: Is it true? Is it kind? Is it necessary?\n\nThe Prophet (SAW) said: 'Whoever believes in Allah and the Last Day, let him speak good or remain silent.' This is not a suggestion — it is a condition of faith.\n\nGuard your tongue, and you will guard your heart. For the words we speak shape the world we live in.",
                "published_date": date.today() - timedelta(days=21),
                "tags": [tag_advice],
            },
            {
                "title": "You Are Never Alone",
                "body": "When the world feels heavy and the path feels long, remember: Allah is closer to you than your jugular vein.\n\nHe hears the prayer you haven't yet spoken. He sees the tear you haven't yet shed. Turn to Him and find that He was already turned towards you.\n\nLoneliness is an illusion of the nafs. The believer who remembers Allah is never alone — even in a crowd of thousands, even in the depths of the night, even in the darkest moment of trial.\n\n'And We are closer to him than his jugular vein.' (Quran 50:16)\n\nSpeak to Him. Pour your heart out in sajdah. He is listening. He always was.",
                "published_date": date.today() - timedelta(days=28),
                "tags": [tag_reminder],
            },
            {
                "title": "The Gift of Gratitude",
                "body": "Shukr is not just saying Alhamdulillah with the tongue. It is feeling it in the bones.\n\nIt is seeing the mercy in the test and the blessing in the breath. When you thank Allah for what you have, He opens doors you never knew existed.\n\n'If you are grateful, I will surely increase you.' (Quran 14:7)\n\nGratitude transforms the ordinary into the extraordinary. The same cup of water, when drunk with gratitude, tastes sweeter. The same roof over your head, when appreciated, feels warmer.\n\nStart a gratitude practice today. Before you sleep, name three blessings. Before you rise, thank Allah for another chance. Watch how your world changes.",
                "published_date": date.today() - timedelta(days=35),
                "tags": [tag_reflection],
            },
            {
                "title": "The Company You Keep",
                "body": "The Prophet (SAW) compared a good companion to a perfume seller — even if you don't buy anything, you will still leave smelling beautiful.\n\nAnd he compared a bad companion to a blacksmith's bellows — even if you are not burned, you will still leave smelling of smoke.\n\nChoose your friends wisely. Surround yourself with those who remind you of Allah, who inspire you to be better, who lift you when you fall.\n\nThe path to Allah is not walked alone. We need companions who strengthen our resolve, who share our vision, who hold us accountable. Find your circle and protect it.",
                "published_date": date.today() - timedelta(days=42),
                "tags": [tag_advice, tag_reflection],
            },
        ]

        for data in writings_data:
            tags = data.pop("tags")
            w = Writing.objects.create(**data)
            w.tags.set(tags)
            self.stdout.write(f"  Created: {w.title}")

        self.stdout.write(self.style.SUCCESS(f"Seed complete: {len(writings_data)} writings."))
