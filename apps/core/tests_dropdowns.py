from django.template import Context, Template
from django.test import SimpleTestCase


def render(source, **ctx):
    return Template("{% load dropdown_tags %}" + source).render(Context(ctx))


def pairs(value):
    """A rendered Python list, with Django's quote escaping undone."""
    return value.replace("&#x27;", "'").replace("&quot;", '"')


class OptsFilterTest(SimpleTestCase):
    def test_value_and_label_are_kept_apart(self):
        self.assertIn("('bug', 'Bug')", pairs(render('{{ "bug:Bug|feature:Feature"|opts }}')))
        self.assertIn("('feature', 'Feature')", pairs(render('{{ "bug:Bug|feature:Feature"|opts }}')))

    def test_a_chunk_without_a_colon_labels_itself(self):
        self.assertIn("('open', 'open')", pairs(render('{{ "open|closed"|opts }}')))

    def test_a_colon_inside_the_label_is_not_split(self):
        self.assertIn("('u', 'Assigned to me')", pairs(render('{{ "u:Assigned to me"|opts }}')))


class DropdownTagTest(SimpleTestCase):
    def test_no_native_select_is_rendered(self):
        html = render('{% dropdown "priority" "low:Low"|opts %}')
        self.assertNotIn("<select", html)
        self.assertIn('type="radio"', html)

    def test_the_current_value_is_prechecked_so_the_key_always_posts(self):
        """A native select always submits its field, including when the value is
        empty. Radios only submit when one is checked, so an unchecked group
        would drop the key entirely and the view would see None instead of "".
        """
        html = render('{% dropdown "priority" "low:Low|medium:Medium"|opts current="medium" %}')
        self.assertIn('value="medium" data-label="Medium" checked', html)

    def test_an_empty_value_becomes_a_real_all_option(self):
        html = render(
            '{% dropdown "status" "open:Open|closed:Closed"|opts current="" '
            'placeholder="All statuses" empty_value="" %}'
        )
        self.assertIn('value="" data-label="All statuses" checked', html)

    def test_the_trigger_shows_the_current_value_without_javascript(self):
        html = render('{% dropdown "status" "open:Open|closed:Closed"|opts current="closed" %}')
        self.assertIn("data-dd-label>Closed<", html)

    def test_the_trigger_falls_back_to_the_placeholder(self):
        html = render(
            '{% dropdown "status" "open:Open"|opts current="" placeholder="All statuses" %}'
        )
        self.assertIn("data-dd-label>All statuses<", html)

    def test_multiple_renders_checkboxes(self):
        html = render(
            '{% dropdown "ids" "1|2"|opts current=ids multiple=True placeholder="Everyone" %}',
            ids=["2"],
        )
        self.assertIn('type="checkbox"', html)
        self.assertIn('value="2" data-label="2" checked', html)
        self.assertNotIn('value="1" data-label="1" checked', html)

    def test_a_single_multiple_choice_does_not_claim_a_selection_of_none(self):
        html = render('{% dropdown "ids" "1|2"|opts current=ids multiple=True %}', ids=[])
        self.assertIn("data-dd-label>All<", html)


class ObjPairsFilterTest(SimpleTestCase):
    class Row:
        def __init__(self, pk, name="", username=""):
            self.pk, self.name, self.username = pk, name, username

        def __str__(self):
            return f"row{self.pk}"

    def test_it_reads_the_named_attributes(self):
        pairs_out = render("{{ rows|obj_pairs:'pk:name' }}", rows=[self.Row(7, name="App")])
        self.assertIn("('7', 'App')", pairs(pairs_out))

    def test_a_blank_label_falls_back_to_username(self):
        out = render("{{ rows|obj_pairs:'pk:name' }}", rows=[self.Row(7, username="alice")])
        self.assertIn("('7', 'alice')", pairs(out))

    def test_a_blank_label_falls_back_to_str(self):
        out = render("{{ rows|obj_pairs:'pk:name' }}", rows=[self.Row(7)])
        self.assertIn("('7', 'row7')", pairs(out))

    def test_a_method_label_is_called_not_repred(self):
        """`get_full_name` is how every member dropdown names a person.

        `str()` on the attribute yields "<bound method ... of <User: bob>>",
        which is what lands in front of every member in the ticket assignee
        filter, the audit-log actor filter and the DSR employee picker.
        """
        class Person(self.Row):
            def get_full_name(self):
                return "Bob Bobson"

        out = render(
            "{{ rows|obj_pairs:'pk:get_full_name' }}", rows=[Person(7)]
        )
        self.assertIn("('7', 'Bob Bobson')", pairs(out))
        self.assertNotIn("bound method", out)

    def test_a_method_label_returning_blank_still_falls_back(self):
        """A member with no full name is the normal case, not an edge case."""

        class Person(self.Row):
            def get_full_name(self):
                return ""

        out = render(
            "{{ rows|obj_pairs:'pk:get_full_name' }}",
            rows=[Person(7, username="bob")],
        )
        self.assertIn("('7', 'bob')", pairs(out))


class ExtraChoicesTest(SimpleTestCase):
    """A filter can mix hand-written sentinels with a real queryset."""

    def test_extra_choices_are_appended_after_the_main_ones(self):
        out = render(
            '{% dropdown "assigned" "me:Assigned to me"|opts '
            'placeholder="All" empty_value="" extra_choices=rows %}',
            rows=[("7", "Bob")],
        )
        self.assertLess(out.index("value=\"me\""), out.index("value=\"7\""))
        self.assertIn("Bob", out)

    def test_the_empty_option_is_still_first(self):
        """It is inserted after the merge, so order stays All -> sentinels -> people."""
        out = render(
            '{% dropdown "assigned" "me:Assigned to me"|opts '
            'placeholder="All assignees" empty_value="" extra_choices=rows %}',
            rows=[("7", "Bob")],
        )
        self.assertLess(out.index("value=\"\""), out.index("value=\"me\""))