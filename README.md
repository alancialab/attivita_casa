# Attività Casa

Integrazione custom per Home Assistant che tiene traccia delle **faccende e manutenzioni ricorrenti di casa** (cambio filtri, pulizie periodiche, annaffiare le piante, ecc.) e ti avvisa quando è il momento di rifarle.

Ogni attività è un'entità `sensor` con stato `ok`, `warning` (scadenza vicina) o `expired` (scaduta), più attributi con i giorni rimanenti, lo storico dei completamenti e la priorità.

## Caratteristiche

- **Due modalità**:
  - `scheduled` (pianificata): l'attività va rifatta ogni N giorni; lo stato diventa `warning` quando la scadenza si avvicina e `expired` quando è passata.
  - `tracker` (monitoraggio): tiene solo traccia di quando è stata fatta l'ultima volta, senza scadenza.
- **Frequenza** configurabile (giorni tra un completamento e il successivo).
- **Priorità** (alta / media / bassa) e **categoria** per organizzare le attività.
- **Storico** degli ultimi completamenti.
- **Binary sensor "scaduta"**: per ogni attività `scheduled` viene creato anche un `binary_sensor` con `device_class: problem`, che diventa `on` quando l'attività è scaduta. Comodo per automazioni e card che vogliono una condizione booleana diretta.
- **Notifiche** opzionali alla scadenza e integrazione con un **calendario** (crea l'evento della prossima scadenza).
- Configurazione interamente da interfaccia (config flow), nessuno YAML.

## Installazione via HACS

1. In HACS → menu in alto a destra → **Custom repositories**.
2. Aggiungi `https://github.com/alancialab/attivita_casa` con categoria **Integration**.
3. Cerca **Attività Casa** in HACS e installa.
4. Riavvia Home Assistant.
5. Vai in **Impostazioni → Dispositivi e servizi → Aggiungi integrazione** e cerca **Attività Casa**.

## Installazione manuale

Copia la cartella `custom_components/attivita_casa/` nella cartella `custom_components/` della tua configurazione Home Assistant, poi riavvia.

## Configurazione

Tutto da interfaccia. Per ogni attività imposti:

| Opzione | Descrizione |
|---|---|
| Nome | Nome dell'attività (es. "Cambio filtri condizionatore") |
| Icona | Icona MDI (default `mdi:checkbox-marked-circle`) |
| Frequenza | Giorni tra un completamento e il successivo (default 30) |
| Modalità | `scheduled` (con scadenza) o `tracker` (solo monitoraggio) |
| Priorità | `high` / `medium` / `low` |
| Categoria | Etichetta libera per raggruppare |
| Notifiche | Servizio notify opzionale alla scadenza |
| Calendario | Entità calendario opzionale per gli eventi di scadenza |

## Servizi

| Servizio | Cosa fa |
|---|---|
| `attivita_casa.reset` | Segna l'attività come completata (oggi o in una data scelta), aggiorna storico e giorni rimanenti; opzionalmente crea l'evento calendario. |
| `attivita_casa.snooze` | Posticipa la scadenza di N giorni senza segnarla completata. |
| `attivita_casa.undo_snooze` | Annulla l'ultimo posticipo e ripristina la scadenza originale. |
| `attivita_casa.set_date` | Imposta manualmente la data dell'ultimo completamento (utile per correzioni). |

## Stati e attributi

- **Stato** (entità `sensor`): `ok`, `warning`, `expired` (per le attività `scheduled`).
- **Binary sensor** (`binary_sensor.<attività>_scaduta`): `on` = scaduta, `off` = non scaduta. Solo per attività `scheduled`.
- **Attributi principali**: nome, giorni rimanenti, ultima data di completamento, storico (ultimi completamenti), priorità, categoria, modalità.

## Licenza

MIT — vedi [LICENSE](LICENSE).
