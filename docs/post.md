# How often can a satellite actually see your field?

Sentinel-2 is a pair of European satellites that photograph the entire land
surface of the planet, for free, every five days. The images are good enough to
pick out individual fields, and anyone can download them without an account.
For anyone trying to monitor a farm from a desk, this sounds like a solved
problem.

Between January 2019 and August 2026 those satellites passed over a 73-hectare
plot near Fundación, in the Colombian department of Magdalena, roughly six
hundred times. I checked how many of those passes produced an image in which the
plot was actually visible.

Three hundred and sixteen. And because clear days cluster together rather than
spreading out evenly, the plot spent 89 % of those seven and a half years with no
usable view at all. On a second, larger plot in the banana corridor near
Aracataca, the figure was 91 %. The longest unbroken stretch without a single
usable image ran from 13 April to 10 July 2024 — eighty-nine consecutive days,
most of a growing cycle.

None of this is surprising to anyone who has worked with optical imagery in the
tropics. Clouds are the oldest complaint in the field. What I found interesting
was how much larger the number turned out to be than the one most workflows
assume, and why.

## The number in the metadata is not the number you want

Every Sentinel-2 image arrives with a field called `eo:cloud_cover`, a
percentage. It is the first thing most pipelines filter on: discard anything
above thirty per cent, keep the rest, build your time series.

That percentage is computed over the whole image, and a Sentinel-2 image covers
110 by 110 kilometres — about twelve thousand square kilometres. The plot near
Fundación is 0.735 square kilometres. It occupies six thousandths of one per cent
of the area that number describes.

The consequence is not a small bias. It is a different measurement entirely.
Clouds in the tropics are patchy at the scale of a kilometre or two, so a scene
covering twelve thousand square kilometres is almost always partly cloudy — the
tile-level figure sits somewhere in the middle nearly every time. A single small
field, by contrast, is usually either underneath a cloud or not. Measured over
the actual polygon, 85 % of observations landed at one extreme or the other:
completely clear, or completely covered. For the tile, only 14 % did.

Filtering by the scene-level number therefore throws away a great deal of
perfectly good data. Across both plots, there were 332 occasions when the scene
value said the image was too cloudy to use and the field itself was entirely
visible. Going the other way — the scene looked fine but the field was obscured —
happened nine times. An asymmetry of roughly thirty-seven to one, and all of it
in the direction of discarding usable observations.

The fix is not complicated. Sentinel-2 products include a per-pixel scene
classification band that labels each 20-metre pixel as vegetation, water, cloud,
cloud shadow, cirrus, and so on. Reading that band inside the field boundary,
rather than trusting a summary computed over an area eighteen thousand times
larger, takes a few lines of code and a windowed read. The tooling to do it has
existed for years. It simply is not what most people do, because the convenient
number is right there in the metadata.

## How much does the answer depend on where you draw the line?

A measurement like this invites an obvious objection: you decided what counts as
"blind", so of course you can make the number whatever you like.

That is worth taking seriously, so I measured it rather than argued about it.
The strict definition counts cloud, cloud shadow, thin cirrus, saturated pixels
and missing data as blocking. Under that reading, the two plots come out at 89 %
and 91 % of days without a usable view.

Loosen it. Thin cirrus is the most debatable category — a high, wispy veil that
may still permit some analyses — and it accounts for a quarter to a third of
everything flagged. Drop it entirely and the figures move to 86 % and 89 %.

Loosen it as far as it can honestly go: count only pixels the classifier is
confident are cloud, and ignore probable cloud, cirrus and shadow altogether.
This is more permissive than any published workflow I am aware of. The result is
82 % and 84 %.

So the answer sits between roughly eighty-two and ninety-one per cent depending
on how generous you are willing to be, and the conclusion is the same at both
ends. That is the useful thing to know: the finding does not rest on the
threshold, and I would rather show the whole range than defend one number.

The usability cutoff behaves the same way. I called an image usable when less
than ten per cent of the field was obscured. Demanding a perfectly clear field
gives 90 % and 92 % blind days; accepting images with half the field covered
gives 87 % and 88 %.

## The cloud mask is a model, and models get revised

While deduplicating the catalogue I noticed that many acquisitions appear twice,
processed under two different versions of ESA's atmospheric correction software.
The sensing timestamps of the two copies differ by one millisecond, which is
enough to defeat any deduplication keyed on time.

The two copies do not always agree about the clouds. Comparing sixty-one such
pairs over the field polygon, eighty per cent were bit-identical. The remaining
twenty per cent differed by an average of about seven per cent of the field area,
and in one case — 29 November 2021 — one version reported the plot completely
clear while the other reported it seventy-two per cent covered. Same satellite,
same acquisition, same pixels. Different software.

About one observation in fifteen crosses the usability threshold depending on
which version you happen to have, and always in the same direction: the newer
processor flags more cloud. Since I keep the newest available version throughout,
the figures above are the conservative end of that range.

This is documented behaviour, not a discovery — ESA states plainly that the
classification thresholds are re-tuned between processing baselines, and there is
a substantial validation literature on how these masks perform. I mention it
because it is easy to work with this data for years without noticing that the
cloud mask carries a version number, and because it puts a floor on how precisely
any measurement of this kind can be stated.

## Radar does not care about clouds

There is a second European satellite programme, Sentinel-1, which carries radar
instead of a camera. Rather than recording sunlight reflected off the surface, it
emits microwave pulses and measures what comes back. Microwaves pass through
cloud. The instrument works at night, in overcast weather, and during storms, and
the data is as free as the optical imagery.

The obvious question is whether its passes happen to fall inside the gaps the
optical record leaves, or whether they cluster on the same clear days for
unrelated reasons. They do not cluster: across both plots there were sixty-six
stretches of fifteen days or more with no usable optical view, and every single
one of them contains at least one radar acquisition. During that eighty-nine-day
blackout in 2024, Sentinel-1 passed over the field twenty-two times.

Whether those passes are *useful* is a separate question, and worth separating
carefully. A radar image is not a substitute for an optical one. Optical sensors
measure reflectance, which relates to pigment and leaf chemistry — that is what
NDVI and its relatives are built on. Radar measures backscatter, which relates to
surface roughness, geometry and moisture. The two answer different questions, and
anyone claiming radar simply fills in for optical is overselling it.

But backscatter does respond to what is growing. To check whether the signal
carried information or was merely present, I extracted the full series over the
banana-corridor plot: 341 acquisitions, all from a single relative orbit, because
radar brightness depends on viewing geometry and mixing orbits manufactures steps
that have nothing to do with the ground.

The series is not noise. Between mid-2021 and late 2023 the plot's mean
backscatter rose by three and a half decibels and then settled at a new level,
where it has stayed. Before and after the transition it is flat.

That rise begins around the time Sentinel-1B failed and was retired, which is
exactly the sort of coincidence that should make you suspicious of your own
result. If the change were a calibration artefact it would disappear when you
restrict the analysis to a single satellite. It does not: measured within
Sentinel-1A alone the slope is slightly steeper, not weaker. The neighbouring
plot, observed by the same satellites on the same orbit through the same
processing chain, moved about eleven times less over the same period.

I should also say what the shape of that change turned out to be, because I got
it wrong at first. My initial write-up described a gradual rise over seven years
and drew a straight line through the data. Comparing four candidate shapes
properly — and charging each one for the breakpoints it needs — the data prefer a
plateau, a transition of roughly two years, and a new plateau, by a very wide
margin over the straight line. That distinction matters for interpretation. A
steady ramp looks like growth. A step between two stable levels looks like an
event.

## What this does not establish

It does not establish what happened on the ground. The radar records that
something changed and dates the transition; it cannot say whether the cause was a
replanting, a change of crop, an irrigation scheme or something else. Confirming
that would require field records.

There is, however, an independent line of evidence pointing the same way. An
earlier optical analysis of the same plot, done separately and without any radar,
found that NDVI dropped in 2021 across three compact blocks with edges following
the property boundaries, recovering by 2025. Straight edges along cadastral lines
indicate management rather than weather. Two instruments, two methods, the same
event, the same dates.

Nor does it establish that radar is generally more abundant than optical. With
Sentinel-1B retired, the single orbit I used delivered about twenty-eight passes
a year between 2022 and 2024, which is fewer than the usable optical images from
those same years. The advantage lies in the complete catalogue — 890 radar passes
across three orbits against 264 usable optical observations — not in any one
orbit. Restricting to one orbit is the right choice for a comparable time series,
and it costs observations.

## Why this might matter to you

If you monitor anything in the humid tropics from orbit, the practical
implication is that your effective revisit is far worse than the nominal
five days, and that filtering on scene-level cloud cover is making it worse still
for no benefit. Reading the classification band inside your own polygon is
cheap and recovers a lot of data.

If you build products that depend on optical observability — yield models, index
insurance, deforestation alerts, anything with a temporal cadence in its
specification — it is worth knowing that a field in the Colombian Caribbean may
go three months without a single usable image, and that this is normal rather
than exceptional.

And if you are somewhere with different weather, the number will be different.
That is rather the point. The tool that produced these figures runs on any
polygon you give it, takes about ninety seconds, and needs no account or API key.

---

The code, the intermediate data and the full method are at
[github.com/EazyHood/cielociego](https://github.com/EazyHood/cielociego), under
MIT. The complete report with all the charts is at
[eazyhood.github.io/cielociego](https://eazyhood.github.io/cielociego/), and the
release is archived at [doi.org/10.5281/zenodo.22132250](https://doi.org/10.5281/zenodo.22132250).

Data is Copernicus Sentinel-2 and Sentinel-1, accessed through the Element84
STAC catalogue on AWS and Microsoft's Planetary Computer. Both are open, and
neither requires registration.
