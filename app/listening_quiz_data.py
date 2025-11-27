# app/listening_quiz_data.py

"""
Static listening quiz data by CEFR level.

Make sure your audio files are placed like:

app/listening_audio/A1/Beginner_A1_Lesson_1_Be_Verbs.mp3
app/listening_audio/A2/L3-01-AbidemiTodd-SavingMoney.mp3
app/listening_audio/B1/L4-01-Do-Emphasis-Languages.mp3
app/listening_audio/B2/Intermediate_5_Lesson_02_Subordinating_Conjunctions_-_Time_KLICKAUD.mp3
app/listening_audio/C1/1536-Tony-Travel.mp3
app/listening_audio/C2/1529-Tahia-UK-Mental-Health.mp3

Adjust the audio_file names below if your filenames differ.
"""

LISTENING_QUIZZES = {
    "C2": [
        {
            "id": "1529-Tahia-UK-Mental-Health",
            "title": "Mental Health",
            "audio_file": "1529-Tahia-UK-Mental-Health.mp3",
            "questions": [
                {
                    "text": "She says _____ experiences mental health issues.",
                    "options": ["few people", "many people", "everybody"],
                    "correct_index": 2,  # c) everybody
                },
                {
                    "text": "She says there are _____ categories of mental health disorders.",
                    "options": ["new", "four", "five"],
                    "correct_index": 2,  # c) five
                },
                {
                    "text": "She says OCD is _____ disorder.",
                    "options": ["an anxiety", "a cognitive", "a psychotic"],
                    "correct_index": 0,  # a) an anxiety
                },
                {
                    "text": "What does he say about fidget toys?",
                    "options": ["He has one.", "He has seen them.", "He has never seen them."],
                    "correct_index": 1,  # b) He has seen them.
                },
                {
                    "text": "Who uses a fidget toy?",
                    "options": ["Her sister", "Her friend", "She does not say"],
                    "correct_index": 0,  # a) Her sister
                },
            ],
        }
    ],

    "C1": [
        {
            "id": "1536-Tony-Travel",
            "title": "Tony – Travel",
            "audio_file": "1536-Tony-Travel.mp3",
            "questions": [
                {
                    "text": "What does he like doing?",
                    "options": ["Flying in planes", "Being in airports", "Planning a vacation"],
                    "correct_index": 0,
                },
                {
                    "text": "What does he like to watch at airports?",
                    "options": ["Pilots", "People", "Airplanes"],
                    "correct_index": 2,
                },
                {
                    "text": "What did he start to like at the age of 5?",
                    "options": ["Planes", "Airports", "Traveling"],
                    "correct_index": 0,
                },
                {
                    "text": "Where has he been before?",
                    "options": ["100 airports", "In the air tower", "In the flight deck"],
                    "correct_index": 2,
                },
                {
                    "text": "What does he do when the pilot speaks?",
                    "options": ["Say a prayer", "Listen carefully", "Read the pamphlet"],
                    "correct_index": 1,
                },
                {
                    "text": "Does the woman have similar or different views while flying?",
                    "options": ["Very similar", "Very different", "She has never flown."],
                    "correct_index": 1,
                },
                {
                    "text": "What does he like to see out the window?",
                    "options": ["The sky", "The wings", "The ground"],
                    "correct_index": 1,
                },
                {
                    "text": "What place has he visited?",
                    "options": ["Spain", "Sweden", "Scotland"],
                    "correct_index": 2,
                },
                {
                    "text": "How many critical phases to a flight does he mention?",
                    "options": ["Two", "Four", "Five"],
                    "correct_index": 2,
                },
                {
                    "text": "Who does he like to talk with?",
                    "options": ["Pilots", "Cabin crew", "Passengers"],
                    "correct_index": 0,
                },
            ],
        }
    ],

    "B2": [
        {
            "id": "Intermediate_5_Lesson_02_Subordinating_Conjunctions_-_Time_KLICKAUD",
            "title": "Soup and Time Conjunctions",
            "audio_file": "Intermediate_5_Lesson_02_Subordinating_Conjunctions_-_Time_KLICKAUD.mp3",
            "questions": [
                {
                    "text": "She cooks the soup and _____ work.",
                    "options": ["brings it", "sells it", "buy it"],
                    "correct_index": 0,
                },
                {
                    "text": "She uses _____ rice.",
                    "options": ["white", "wild", "brown"],
                    "correct_index": 2,
                },
                {
                    "text": "She often adds _____.",
                    "options": ["onions", "garlic", "celery"],
                    "correct_index": 1,
                },
                {
                    "text": "She lets it sit until it _____.",
                    "options": ["gets cold", "is room temperature", "hardens"],
                    "correct_index": 1,
                },
                {
                    "text": "She usually makes enough for _____ bowls.",
                    "options": ["three", "six", "nine"],
                    "correct_index": 0,
                },
            ],
        }
    ],

    "B1": [
        {
            "id": "L4-01-Do-Emphasis-Languages",
            "title": "Do / Emphasis – Languages",
            "audio_file": "L4-01-Do-Emphasis-Languages.mp3",
            "questions": [
                {
                    "text": "Who taught in Mexico?",
                    "options": ["Todd", "Sarah", "Neither of them"],
                    "correct_index": 1,
                },
                {
                    "text": "Who studied Korean?",
                    "options": ["Todd", "Sarah", "Both of them"],
                    "correct_index": 1,
                },
                {
                    "text": "Who taught in Korea?",
                    "options": ["Todd", "Sarah", "Both of them"],
                    "correct_index": 1,
                },
                {
                    "text": "Who speaks Thai?",
                    "options": ["Todd", "Sarah", "Both of them"],
                    "correct_index": 0,
                },
                {
                    "text": "Who speaks Japanese?",
                    "options": ["Todd", "Sarah", "Both of them"],
                    "correct_index": 0,
                },
            ],
        }
    ],

    "A2": [
        {
            "id": "L3-01-AbidemiTodd-SavingMoney",
            "title": "Saving Money",
            "audio_file": "L3-01-AbidemiTodd-SavingMoney.mp3",
            "questions": [
                {
                    "text": "Who is good at saving money?",
                    "options": ["She is.", "He is.", "Neither of them."],
                    "correct_index": 0,
                },
                {
                    "text": "Who wastes a lot of money on food?",
                    "options": ["He does.", "She does.", "Neither of them."],
                    "correct_index": 0,
                },
                {
                    "text": "What does she waste money on?",
                    "options": ["Eating out", "Clothes", "Gifts"],
                    "correct_index": 1,
                },
                {
                    "text": "How does he save money on clothes?",
                    "options": ["He asks for gifts", "He looks for sales", "He buys used clothing"],
                    "correct_index": 0,
                },
                {
                    "text": "Who talks about money and travelling?",
                    "options": ["Just her.", "Just him.", "Both of them"],
                    "correct_index": 2,
                },
            ],
        }
    ],

    "A1": [
        {
            "id": "Beginner_A1_Lesson_1_Be_Verbs",
            "title": "Be Verbs – Basic Info",
            "audio_file": "Beginner_A1_Lesson_1_Be_Verbs.mp3",
            "questions": [
                {
                    "text": "Where is he from?",
                    "options": ["The east coast", "The west coast", "The south coast"],
                    "correct_index": 1,
                },
                {
                    "text": "How old is he?",
                    "options": ["45", "46", "47"],
                    "correct_index": 2,
                },
                {
                    "text": "Where is she from?",
                    "options": ["Edinburgh", "Aberdeen", "Glasgow"],
                    "correct_index": 2,
                },
                {
                    "text": "Who is a teacher?",
                    "options": ["Her mom", "Her dad", "Her aunt"],
                    "correct_index": 1,
                },
            ],
        }
    ],
}
