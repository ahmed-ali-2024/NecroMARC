export interface MarcSource {
  id: string;
  url: string;
  nameKey: string;
  noteKey: string;
}

/** External places where visitors can find downloadable MARC 21 (.mrc) files. */
export const MARC_SOURCES: readonly MarcSource[] = [
  {
    id: 'gutenberg-au',
    url: 'https://gutenberg.net.au/marc.html',
    nameKey: 'sources.gutenberg.name',
    noteKey: 'sources.gutenberg.note',
  },
  {
    id: 'boa',
    url: 'https://britishonlinearchives.com/librarian-resources/marc-21-records',
    nameKey: 'sources.boa.name',
    noteKey: 'sources.boa.note',
  },
  {
    id: 'obp',
    url: 'https://www.openbookpublishers.com/libraries/marc-records',
    nameKey: 'sources.obp.name',
    noteKey: 'sources.obp.note',
  },
] as const;
