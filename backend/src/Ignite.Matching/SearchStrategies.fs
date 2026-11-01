module Ignite.Matching.SearchStrategies

open System

let getSearchStrategies (artist: string) (title: string) (album: string option) =
    seq {
        match album with
        | Some a when not (String.IsNullOrWhiteSpace a) ->
            ($"artist:{artist} track:{title} album:{a}", "artist+title+album")
        | _ -> ()

        ($"artist:{artist} track:{title}", "artist+title")

        let cleanArtist = StringNormalization.removeFeaturingArtists artist

        if cleanArtist <> artist then
            ($"artist:{cleanArtist} track:{title}", "clean_artist+title")

        let pipeParts = artist.Split('|', StringSplitOptions.TrimEntries)

        if pipeParts.Length > 1 then
            for part in pipeParts do
                ($"artist:{part} track:{title}", "pipe_separated")

        let cleanTitle = StringNormalization.removeParenthetical title

        if cleanTitle <> title then
            ($"artist:{artist} track:{cleanTitle}", "clean_title")

        if cleanArtist <> artist && cleanTitle <> title then
            ($"artist:{cleanArtist} track:{cleanTitle}", "clean_both")

        let expandedTitle = StringNormalization.expandContractions title

        if expandedTitle <> title then
            ($"artist:{artist} track:{expandedTitle}", "expanded_title")

        let contractedTitle = StringNormalization.contractExpansions title

        if contractedTitle <> title then
            ($"artist:{artist} track:{contractedTitle}", "contracted_title")

        ($"{artist} {title}", "simple")
    }
