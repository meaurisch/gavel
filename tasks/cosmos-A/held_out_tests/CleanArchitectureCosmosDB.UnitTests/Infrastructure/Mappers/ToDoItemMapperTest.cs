using CleanArchitectureCosmosDB.Core.Entities;
using CleanArchitectureCosmosDB.Infrastructure.CosmosDbData.Mappers;
using CleanArchitectureCosmosDB.Infrastructure.CosmosDbData.Models;
using Xunit;

namespace CleanArchitectureCosmosDB.UnitTests.Infrastructure.Mappers
{
    public class ToDoItemMapperTest
    {
        [Fact]
        public void ToDocument_MapsAllProperties()
        {
            var entity = new ToDoItem
            {
                Id = "cat:123",
                Category = "cat",
                Title = "Test Title"
            };
            entity.MarkComplete();

            var document = ToDoItemMapper.ToDocument(entity);

            Assert.Equal("cat:123", document.Id);
            Assert.Equal("cat", document.Category);
            Assert.Equal("Test Title", document.Title);
            Assert.True(document.IsCompleted);
            Assert.Equal("todoitem", document.Type);
        }

        [Fact]
        public void ToDomain_MapsAllProperties()
        {
            var document = new ToDoItemDocument
            {
                Id = "cat:456",
                Category = "cat",
                Title = "Another Title",
                IsCompleted = true,
                Type = "todoitem",
                Etag = "some-etag"
            };

            var entity = ToDoItemMapper.ToDomain(document);

            Assert.Equal("cat:456", entity.Id);
            Assert.Equal("cat", entity.Category);
            Assert.Equal("Another Title", entity.Title);
            Assert.True(entity.IsCompleted);
        }

        [Fact]
        public void ToDomain_HandlesIsCompletedFalse()
        {
            var document = new ToDoItemDocument
            {
                Id = "cat:789",
                Category = "cat",
                Title = "Not Done",
                IsCompleted = false
            };

            var entity = ToDoItemMapper.ToDomain(document);

            Assert.False(entity.IsCompleted);
        }

        [Fact]
        public void Roundtrip_PreservesData()
        {
            var original = new ToDoItem
            {
                Id = "work:001",
                Category = "work",
                Title = "Roundtrip Test"
            };
            original.MarkComplete();

            var document = ToDoItemMapper.ToDocument(original);
            var restored = ToDoItemMapper.ToDomain(document);

            Assert.Equal(original.Id, restored.Id);
            Assert.Equal(original.Category, restored.Category);
            Assert.Equal(original.Title, restored.Title);
            Assert.Equal(original.IsCompleted, restored.IsCompleted);
        }
    }
}
