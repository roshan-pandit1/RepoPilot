"use client";

import { useId, useRef, useState } from "react";
import type { Repository } from "@/lib/types";
import { Icon } from "./ui";

export function filterRepositories(repositories: Repository[], query: string) {
  const normalized = query.trim().toLocaleLowerCase();
  return repositories.filter(repository => repository.full_name.toLocaleLowerCase().includes(normalized));
}

export function nextRepositoryIndex(current: number, count: number, direction: 1 | -1) {
  return count ? (current + direction + count) % count : -1;
}

export function RepositorySelector({ repositories, selected, onSelect }: { repositories: Repository[]; selected: string; onSelect: (id: string) => void }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(-1);
  const input = useRef<HTMLInputElement>(null);
  const listId = useId();
  const selectedName = repositories.find(repository => repository.id === selected)?.full_name ?? "";
  const matches = filterRepositories(repositories, query);
  const activeId = open && active >= 0 && active < matches.length ? `${listId}-${active}` : undefined;

  function choose(id: string) {
    if (id !== selected) onSelect(id);
    setQuery("");
    setActive(-1);
    setOpen(false);
    input.current?.focus();
  }

  return <div className="repository-selector" onBlur={event => {
    if (!event.currentTarget.contains(event.relatedTarget)) { setOpen(false); setActive(-1); setQuery(""); }
  }}>
    <div className="repository-selector-control">
      <Icon name="repository" className="repository-selector-icon" />
      <label htmlFor="repository-selector" className="sr-only">Select repository</label>
      <input ref={input} id="repository-selector" name="repository" role="combobox" type="text"
        autoComplete="off" aria-autocomplete="list" aria-expanded={open} aria-controls={open ? listId : undefined}
        aria-activedescendant={activeId} disabled={!repositories.length} placeholder={repositories.length ? "Search repositories" : "No repositories yet"}
        value={open ? query : selectedName} onFocus={() => { setOpen(true); setQuery(""); setActive(-1); }}
        onChange={event => { setQuery(event.target.value); setOpen(true); setActive(-1); }}
        onKeyDown={event => {
          if (event.key === "ArrowDown" || event.key === "ArrowUp") {
            event.preventDefault(); setOpen(true);
            setActive(index => nextRepositoryIndex(index < 0 && event.key === "ArrowUp" ? 0 : index, matches.length, event.key === "ArrowDown" ? 1 : -1));
          } else if (event.key === "Enter" && open && active >= 0 && matches[active]) {
            event.preventDefault(); choose(matches[active].id);
          } else if (event.key === "Escape" && open) {
            event.preventDefault(); setOpen(false); setActive(-1); setQuery("");
          }
        }} />
      <button type="button" className="repository-selector-toggle" aria-label={open ? "Close repository list" : "Open repository list"}
        aria-expanded={open} aria-controls={open ? listId : undefined} disabled={!repositories.length}
        onMouseDown={event => event.preventDefault()} onClick={() => { if (open) { setOpen(false); setQuery(""); setActive(-1); } else { setOpen(true); setQuery(""); input.current?.focus(); } }}>
        <Icon name="chevron" width="17" height="17" />
      </button>
    </div>
    {open && <ul id={listId} role="listbox" aria-label="Repositories" className="repository-selector-list">
      {matches.length ? matches.map((repository, index) => <li key={repository.id} id={`${listId}-${index}`} role="option"
        aria-selected={repository.id === selected} data-active={index === active} onMouseDown={event => event.preventDefault()}
        onMouseEnter={() => setActive(index)} onClick={() => choose(repository.id)}>
        <Icon name="repository" width="16" height="16" /><span>{repository.full_name}</span>{repository.id === selected && <Icon name="check" width="16" height="16" />}
      </li>) : <li role="presentation" className="repository-selector-empty">No matching repositories</li>}
    </ul>}
  </div>;
}
