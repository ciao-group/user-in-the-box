from uitb import Simulator
import sys
import gymnasium as gym
import importlib

# Pfad zur Konfigurationsdatei definieren
config_file = "/Users/juliette-michelleburkhardt/PycharmProjects/user-in-the-box/uitb/configs/mobl_arms_index_pointing.yaml"

# Simulator bauen
simulator_folder = Simulator.build(config_file)

# Simulator-Ordner zum Python-Pfad hinzufügen, um sicherzustellen, dass es beim Importieren gefunden wird
sys.path.insert(0, simulator_folder)

# Importieren des Moduls, das die Gym-Umgebung registriert.
# Stellen Sie sicher, dass der Name des Moduls korrekt ist.
# Der Modulname sollte übereinstimmen mit dem, was in der '__init__.py' innerhalb des simulators-Ordners definiert ist,
# der nach dem Bauen des Simulators erstellt wurde.
# Diese Zeile ist kritisch, da sie die Registrierung der Umgebung bei Gym auslöst.
importlib.import_module("mobl_arms_index_pointing")

# Alle verfügbaren Umgebungen auflisten, um sicherzustellen, dass die Registrierung erfolgreich war
print("Verfügbare Umgebungen nach der Registrierung:")
for env_id in gym.envs.registry.keys():
    print(env_id)

# Versuchen, die Simulator-Umgebung zu initialisieren
try:
    simulator = gym.make("uitb:mobl_arms_index_pointing-v0")
    print("Simulator erfolgreich initialisiert.")
except gym.error.UnregisteredEnv as e:
    print(f"Fehler: Die Umgebung konnte nicht gefunden werden. Details: {e}")
