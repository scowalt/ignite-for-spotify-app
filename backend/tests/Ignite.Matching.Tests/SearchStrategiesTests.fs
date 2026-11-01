module Ignite.Matching.Tests.SearchStrategiesTests

open Xunit
open Ignite.Matching.SearchStrategies

[<Fact>]
let ``getSearchStrategies with album includes album strategy`` () =
    let strategies = getSearchStrategies "Artist" "Title" (Some "Album") |> Seq.toList
    Assert.Equal("artist:Artist track:Title album:Album", fst strategies[0])
    Assert.Equal("artist+title+album", snd strategies[0])
    Assert.Equal("artist:Artist track:Title", fst strategies[1])
    Assert.Equal("artist+title", snd strategies[1])

[<Fact>]
let ``getSearchStrategies without album skips album strategy`` () =
    let strategies = getSearchStrategies "Artist" "Title" None |> Seq.toList
    Assert.Equal("artist:Artist track:Title", fst strategies[0])
    Assert.Equal("artist+title", snd strategies[0])

[<Fact>]
let ``getSearchStrategies with featuring includes clean artist strategy`` () =
    let strategies = getSearchStrategies "Artist ft. Someone" "Title" None |> Seq.toList
    let cleanArtist = strategies |> List.find (fun (_, s) -> s = "clean_artist+title")
    Assert.Equal("artist:Artist track:Title", fst cleanArtist)

[<Fact>]
let ``getSearchStrategies without featuring skips clean artist strategy`` () =
    let strategies = getSearchStrategies "Artist" "Title" None |> Seq.toList
    Assert.DoesNotContain("clean_artist+title", strategies |> List.map snd)

[<Fact>]
let ``getSearchStrategies with pipe separated artist includes pipe strategies`` () =
    let strategies = getSearchStrategies "Name | Имя" "Title" None |> Seq.toList
    let pipeStrategies = strategies |> List.filter (fun (_, s) -> s = "pipe_separated")
    Assert.Equal(2, pipeStrategies.Length)
    Assert.Equal("artist:Name track:Title", fst pipeStrategies[0])
    Assert.Equal("artist:Имя track:Title", fst pipeStrategies[1])

[<Fact>]
let ``getSearchStrategies with parenthetical includes clean title strategy`` () =
    let strategies = getSearchStrategies "Artist" "Song (Live)" None |> Seq.toList
    let cleanTitle = strategies |> List.find (fun (_, s) -> s = "clean_title")
    Assert.Equal("artist:Artist track:Song", fst cleanTitle)

[<Fact>]
let ``getSearchStrategies without parenthetical skips clean title strategy`` () =
    let strategies = getSearchStrategies "Artist" "Title" None |> Seq.toList
    Assert.DoesNotContain("clean_title", strategies |> List.map snd)

[<Fact>]
let ``getSearchStrategies with featuring and parenthetical includes clean both strategy`` () =
    let strategies = getSearchStrategies "Artist ft. Someone" "Song (Live)" None |> Seq.toList
    let cleanBoth = strategies |> List.find (fun (_, s) -> s = "clean_both")
    Assert.Equal("artist:Artist track:Song", fst cleanBoth)

[<Fact>]
let ``getSearchStrategies with contraction includes expanded strategy`` () =
    let strategies = getSearchStrategies "Artist" "Don't Stop" None |> Seq.toList
    let expanded = strategies |> List.find (fun (_, s) -> s = "expanded_title")
    Assert.Equal("artist:Artist track:do not Stop", fst expanded)

[<Fact>]
let ``getSearchStrategies with expansion includes contracted strategy`` () =
    let strategies = getSearchStrategies "Artist" "Do Not Stop" None |> Seq.toList
    let contracted = strategies |> List.find (fun (_, s) -> s = "contracted_title")
    Assert.Equal("artist:Artist track:don't Stop", fst contracted)

[<Fact>]
let ``getSearchStrategies always ends with simple fallback`` () =
    let strategies = getSearchStrategies "Artist" "Title" None |> Seq.toList
    let last = strategies |> List.last
    Assert.Equal("Artist Title", fst last)
    Assert.Equal("simple", snd last)

[<Fact>]
let ``getSearchStrategies full sequence standard case`` () =
    let strategies = getSearchStrategies "Artist" "Title" (Some "Album") |> Seq.toList
    let names = strategies |> List.map snd
    Assert.Equal<string list>([ "artist+title+album"; "artist+title"; "simple" ], names)

[<Fact>]
let ``getSearchStrategies full sequence complex case`` () =
    let strategies = getSearchStrategies "Artist ft. Band" "Don't Stop (Live)" (Some "Album") |> Seq.toList
    let names = strategies |> List.map snd
    Assert.Contains("artist+title+album", names)
    Assert.Contains("artist+title", names)
    Assert.Contains("clean_artist+title", names)
    Assert.Contains("clean_title", names)
    Assert.Contains("clean_both", names)
    Assert.Contains("expanded_title", names)
    Assert.Contains("simple", names)
