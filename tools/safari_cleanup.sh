#!/usr/bin/env bash

set -u

USER_ID=$(id -u)
PROCESS_NAMES=(Safari safaridriver)

wait_for_processes_to_exit() {
  local attempts=$1
  shift
  local process_name

  while (( attempts > 0 )); do
    for process_name in "$@"; do
      if pgrep -u "$USER_ID" -x "$process_name" > /dev/null; then
        sleep 1
        attempts=$((attempts - 1))
        continue 2
      fi
    done

    return 0
  done

  return 1
}

print_process_state() {
  local process_name=$1
  local process_ids

  if process_ids=$(pgrep -u "$USER_ID" -x "$process_name"); then
    printf 'Process state for %s:\n' "$process_name" >&2
    ps -p "$(printf '%s\n' "$process_ids" | paste -sd, -)" -o pid,ppid,stat,start,time,comm >&2
  else
    printf '%s not running\n' "$process_name" >&2
  fi
}

signal_processes() {
  local signal_name=$1
  shift
  local process_name
  local process_ids

  for process_name in "$@"; do
    if process_ids=$(pgrep -u "$USER_ID" -x "$process_name"); then
      printf 'Sending %s to %s (pids: %s)\n' "$signal_name" "$process_name" "$(printf '%s\n' "$process_ids" | paste -sd, -)" >&2
      pkill -"$signal_name" -u "$USER_ID" -x "$process_name" || printf 'Failed to send %s to %s\n' "$signal_name" "$process_name" >&2
    fi
  done
}

main() {
  # Leave WebKit helper processes to Safari/macOS lifecycle management instead of broad process matching.
  signal_processes TERM "${PROCESS_NAMES[@]}"

  if ! wait_for_processes_to_exit 15 "${PROCESS_NAMES[@]}"; then
    printf 'Safari or safaridriver still running after TERM wait\n' >&2
    for process_name in "${PROCESS_NAMES[@]}"; do
      print_process_state "$process_name"
    done
  fi

  signal_processes KILL "${PROCESS_NAMES[@]}"

  if ! wait_for_processes_to_exit 5 "${PROCESS_NAMES[@]}"; then
    printf 'Safari or safaridriver still running after KILL wait\n' >&2
    for process_name in "${PROCESS_NAMES[@]}"; do
      print_process_state "$process_name"
    done
  fi

  if pgrep -u "$USER_ID" -x safaridriver > /dev/null; then
    printf 'safaridriver still running after cleanup\n' >&2
    print_process_state safaridriver
    exit 1
  fi
}

main "$@"
