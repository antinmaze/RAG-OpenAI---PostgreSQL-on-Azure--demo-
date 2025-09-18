import asyncio
import random

from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from fastapi_app.dependencies import get_azure_credential
from fastapi_app.postgres_engine import create_postgres_engine_from_env
from fastapi_app.postgres_models import Item

# Liste d'acteurs célèbres et personnages historiques respectés par nationalité
CELEBRITIES_AND_HISTORICAL_FIGURES = [
    # Acteurs américains
    "Leonardo DiCaprio",
    "Robert De Niro",
    "Tom Hanks",
    "Meryl Streep",
    "Denzel Washington",
    "Jennifer Lawrence",
    "Brad Pitt",
    "Scarlett Johansson",
    "Will Smith",
    "Julia Roberts",
    "Morgan Freeman",
    "Sandra Bullock",
    "Johnny Depp",
    "Angelina Jolie",
    "Samuel L. Jackson",
    # Acteurs espagnols
    "Penélope Cruz",
    "Antonio Banderas",
    "Javier Bardem",
    "Paz Vega",
    "Jordi Mollà",
    "Elena Anaya",
    "Eduard Fernández",
    "Úrsula Corberó",
    "Álvaro Morte",
    "María Valverde",
    # Acteurs anglais
    "Daniel Craig",
    "Emma Watson",
    "Benedict Cumberbatch",
    "Kate Winslet",
    "Hugh Grant",
    "Helena Bonham Carter",
    "Gary Oldman",
    "Keira Knightley",
    "Colin Firth",
    "Tilda Swinton",
    "Ralph Fiennes",
    "Emily Blunt",
    "Tom Hardy",
    "Carey Mulligan",
    # Acteurs français
    "Marion Cotillard",
    "Jean Reno",
    "Audrey Tautou",
    "Vincent Cassel",
    "Léa Seydoux",
    "Omar Sy",
    "Catherine Deneuve",
    "Gérard Depardieu",
    "Juliette Binoche",
    "Jean Dujardin",
    "Isabelle Huppert",
    "François Cluzet",
    "Mathieu Amalric",
    "Mélanie Laurent",
    # Personnages historiques - Scientifiques et inventeurs
    "Albert Einstein",
    "Marie Curie",
    "Leonardo da Vinci",
    "Isaac Newton",
    "Galileo Galilei",
    "Charles Darwin",
    "Thomas Edison",
    "Nikola Tesla",
    "Alexander Fleming",
    "Louis Pasteur",
    "Gregor Mendel",
    "Johannes Kepler",
    "Archimedes",
    "Hippocrates",
    # Personnages historiques - Explorateurs et aventuriers
    "Marco Polo",
    "Christopher Columbus",
    "Vasco da Gama",
    "Ferdinand Magellan",
    "James Cook",
    "Ernest Shackleton",
    "Roald Amundsen",
    "Jacques Cousteau",
    "Yuri Gagarin",
    "Neil Armstrong",
    "Buzz Aldrin",
    "Amelia Earhart",
    # Personnages historiques - Artistes et compositeurs
    "Wolfgang Amadeus Mozart",
    "Ludwig van Beethoven",
    "Johann Sebastian Bach",
    "Frédéric Chopin",
    "Antonio Vivaldi",
    "Claude Monet",
    "Vincent van Gogh",
    "Pablo Picasso",
    "Michelangelo",
    "Auguste Rodin",
    "Salvador Dalí",
    "Henri Matisse",
    "Edgar Degas",
    "Paul Cézanne",
    # Personnages historiques - Écrivains et philosophes
    "William Shakespeare",
    "Victor Hugo",
    "Charles Dickens",
    "Jane Austen",
    "Mark Twain",
    "Jules Verne",
    "Alexandre Dumas",
    "Molière",
    "Voltaire",
    "Jean-Jacques Rousseau",
    "Socrates",
    "Plato",
    "Aristotle",
    "Confucius",
    # Personnages historiques - Leaders pacifiques et humanitaires
    "Mahatma Gandhi",
    "Martin Luther King Jr.",
    "Nelson Mandela",
    "Mother Teresa",
    "Eleanor Roosevelt",
    "Florence Nightingale",
    "Clara Barton",
    "Jane Addams",
    "Wangari Maathai",
    "Malala Yousafzai",
    # Personnages historiques - Autres pays
    "Sun Yat-sen",  # Chine
    "Akira Kurosawa",  # Japon
    "Frida Kahlo",  # Mexique
    "Paulo Coelho",  # Brésil
    "Ibn Sina (Avicenna)",  # Perse
    "Omar Khayyam",  # Perse
    "Al-Khwarizmi",  # Perse
    "Ibn Rushd (Averroes)",  # Andalousie
    "Rumi",  # Perse
    "Hafez",  # Perse
    "Rabindranath Tagore",  # Inde
    "A.P.J. Abdul Kalam",  # Inde
    "Carlos Slim",  # Mexique
    "Gabriel García Márquez",  # Colombie
    "Jorge Luis Borges",  # Argentine
    "Pelé",  # Brésil
    "Diego Rivera",  # Mexique
]


async def update_owners_with_celebrities():
    """Met à jour la colonne owner avec des noms d'acteurs célèbres et personnages historiques respectés"""
    azure_credential = await get_azure_credential()
    engine = await create_postgres_engine_from_env(azure_credential)

    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        async with session.begin():
            # Récupérer tous les items
            result = await session.execute(select(Item))
            items = result.scalars().all()

            print(f"Mise à jour de {len(items)} items avec des noms d'acteurs célèbres et personnages historiques...")

            # Mélanger la liste pour plus de randomisation
            random.shuffle(CELEBRITIES_AND_HISTORICAL_FIGURES)

            for i, item in enumerate(items):
                # Assigner une personnalité de manière cyclique pour assurer une bonne distribution
                celebrity = CELEBRITIES_AND_HISTORICAL_FIGURES[i % len(CELEBRITIES_AND_HISTORICAL_FIGURES)]
                item.owner = celebrity
                print(f"Item {item.id}: {item.name} -> Owner: {celebrity}")

            await session.commit()
            print(
                f"✅ Mise à jour terminée! {len(items)} items mis à jour avec des "
                f"acteurs célèbres et personnages historiques respectés."
            )


if __name__ == "__main__":
    load_dotenv(override=True)
    asyncio.run(update_owners_with_celebrities())
