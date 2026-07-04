from bang_game import info_extract, create_players, Juego


def main():
    cartas_csv = "cartas.csv"
    personajes_csv = "personajes.txt"
    roles_csv = "roles.txt"

    baraja, personajes, roles = info_extract(cartas_csv, personajes_csv, roles_csv)

    while True:
        num_jugadores = input("¿Cuántos jugadores sois? (4-7): ").strip()
        if num_jugadores.isdigit() and int(num_jugadores) in {4, 5, 6, 7}:
            num_jugadores = int(num_jugadores)
            break
        print("Introduce un número válido entre 4 y 7")

    nombres = []
    for i in range(num_jugadores):
        nombre = input(f"Nombre del jugador {i+1}: ").strip()
        nombres.append(nombre or f"Jugador{i+1}")

    jugadores = create_players(num_jugadores, nombres, personajes, roles)
    juego = Juego(jugadores, baraja)

    print(juego)
    juego.partida()


if __name__ == "__main__":
    main()
