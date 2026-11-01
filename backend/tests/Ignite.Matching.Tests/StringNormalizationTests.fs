module Ignite.Matching.Tests.StringNormalizationTests

open Xunit
open Ignite.Matching.StringNormalization

[<Theory>]
[<InlineData("Artist ft. Someone", "Artist")>]
[<InlineData("Artist feat. Someone", "Artist")>]
[<InlineData("Artist feat Someone", "Artist")>]
[<InlineData("Artist featuring Someone", "Artist")>]
[<InlineData("Artist ft Someone", "Artist")>]
[<InlineData("Artist & Someone", "Artist")>]
[<InlineData("Artist and Someone", "Artist")>]
[<InlineData("Artist Ft. Someone", "Artist")>]
[<InlineData("Artist Feat. Someone", "Artist")>]
[<InlineData("Artist Featuring Someone", "Artist")>]
let ``removeFeaturingArtists removes all patterns`` (input: string, expected: string) =
    Assert.Equal(expected, removeFeaturingArtists input)

[<Theory>]
[<InlineData("Artist", "Artist")>]
[<InlineData("The Band", "The Band")>]
let ``removeFeaturingArtists no change when no featuring pattern`` (input: string, expected: string) =
    Assert.Equal(expected, removeFeaturingArtists input)

[<Theory>]
[<InlineData("Song (Live)", "Song")>]
[<InlineData("Song [Deluxe]", "Song")>]
[<InlineData("Song {Bonus}", "Song")>]
[<InlineData("Song (Remix) [Live]", "Song")>]
[<InlineData("Song", "Song")>]
let ``removeParenthetical removes bracketed content`` (input: string, expected: string) =
    Assert.Equal(expected, removeParenthetical input)

[<Theory>]
[<InlineData("I'm happy", "I am happy")>]
[<InlineData("you're great", "you are great")>]
[<InlineData("don't stop", "do not stop")>]
[<InlineData("won't fail", "will not fail")>]
[<InlineData("can't do", "cannot do")>]
[<InlineData("I'll be", "I will be")>]
[<InlineData("I've been", "I have been")>]
[<InlineData("I'd like", "I would like")>]
let ``expandContractions expands all patterns`` (input: string, expected: string) =
    Assert.Equal(expected, expandContractions input)

[<Fact>]
let ``expandContractions is case insensitive`` () =
    Assert.Equal("I am happy", expandContractions "I'M happy")
    Assert.Equal("do not stop", expandContractions "DON'T stop")

[<Fact>]
let ``expandContractions respects word boundaries`` () =
    Assert.Equal("no change", expandContractions "no change")

[<Theory>]
[<InlineData("I am happy", "I'm happy")>]
[<InlineData("you are great", "you're great")>]
[<InlineData("do not stop", "don't stop")>]
[<InlineData("will not fail", "won't fail")>]
[<InlineData("cannot do", "can't do")>]
[<InlineData("is not right", "isn't right")>]
[<InlineData("have not seen", "haven't seen")>]
let ``contractExpansions contracts all patterns`` (input: string, expected: string) =
    Assert.Equal(expected, contractExpansions input)

[<Fact>]
let ``contractExpansions is case insensitive`` () =
    Assert.Equal("don't stop", contractExpansions "DO NOT stop")
