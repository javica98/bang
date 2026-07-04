from bang_game import info_extract, create_players, Juego, build_player_names
from bang_pygame_io import PygameIO


def main():
    cartas_csv = "cartas.csv"
    personajes_csv = "personajes.txt"
    roles_csv = "roles.txt"

    baraja, personajes, roles = info_extract(cartas_csv, personajes_csv, roles_csv)

    io = PygameIO()

    num_jugadores = int(io.prompt("¿Cuántos jugadores sois?", options=["4", "5", "6", "7"]))

    nombres = build_player_names(num_jugadores, io=io)

    jugadores = create_players(num_jugadores, nombres, personajes, roles, io=io)
    juego = Juego(jugadores, baraja, io=io)
    io.set_game(juego)

    print(juego)
    juego.partida()


if __name__ == "__main__":
    main()
