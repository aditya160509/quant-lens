import React, { useEffect, useState } from 'react';
import * as Select from '@radix-ui/react-select';
import { getWatchlists, createWatchlist } from '@/lib/api';
import { ChevronDown, Plus } from 'lucide-react';

export default function WatchlistSelector({ onSelect }) {
    const [watchlists, setWatchlists] = useState([]);
    const [selected, setSelected] = useState("");

    useEffect(() => {
        loadWatchlists();
    }, []);

    const loadWatchlists = async () => {
        try {
            const data = await getWatchlists();
            setWatchlists(data);
            if (data.length > 0) {
                setSelected(data[0].id);
                if (onSelect) onSelect(data[0]);
            }
        } catch (e) {
            console.error("Failed to load watchlists", e);
        }
    };

    const handleValueChange = (val) => {
        setSelected(val);
        const wl = watchlists.find(w => w.id === val);
        if (onSelect) onSelect(wl);
    };

    return (
        <Select.Root value={selected} onValueChange={handleValueChange}>
            <Select.Trigger className="inline-flex items-center justify-between rounded px-3 py-1.5 text-sm leading-none h-8 gap-2 bg-terminal-darker border border-terminal-dark-gray text-terminal-text hover:bg-terminal-dark focus:outline-none focus:border-terminal-green w-[180px]">
                <Select.Value placeholder="Select Watchlist" />
                <Select.Icon>
                    <ChevronDown className="h-4 w-4" />
                </Select.Icon>
            </Select.Trigger>
            <Select.Portal>
                <Select.Content className="overflow-hidden bg-terminal-darker rounded-md border border-terminal-dark-gray shadow-lg z-50">
                    <Select.Viewport className="p-1">
                        {watchlists.map((wl) => (
                            <Select.Item key={wl.id} value={wl.id} className="text-sm leading-none text-terminal-text rounded flex items-center h-8 px-6 relative select-none data-[highlighted]:bg-terminal-dark data-[highlighted]:text-terminal-green outline-none cursor-pointer">
                                <Select.ItemText>{wl.name}</Select.ItemText>
                            </Select.Item>
                        ))}
                    </Select.Viewport>
                </Select.Content>
            </Select.Portal>
        </Select.Root>
    );
}
